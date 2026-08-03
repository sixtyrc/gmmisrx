# Despliegue en el Windows Server + automatización con GitHub Actions

> Server destino: Windows Server (VPS), ya corre Caddy (reverse proxy/HTTPS) + NSSM (procesos persistentes) para otras apps Django/React. Este documento asume esos dos ya están instalados; si no, instalarlos primero (`choco install caddy`, o binario directo; NSSM desde nssm.cc).

## Arquitectura del despliegue

```
GitHub (push a main)
   │
   ▼
Self-hosted runner de GitHub Actions (corre EN el mismo Windows Server)
   │  git pull + pip install + migrate + reiniciar servicio
   ▼
Servicio NSSM "gmmisrx-panel" ── waitress (WSGI) ── Django (padron + processor)
   │
   ▼
Caddy (reverse proxy HTTPS) ← usuarios entran por acá

Aparte, sin relación con el push:
Windows Task Scheduler ── scripts/run_actualizar_padron.bat ── 15:30 hs ── actualizar_padron --trigger automatico
```

Dos mecanismos separados a propósito:
- **NSSM**: el panel web, un proceso que queda corriendo siempre (como sus otras apps).
- **Task Scheduler**: la actualización diaria del padrón, un job que corre y termina (no debe quedar como servicio).
- **Self-hosted runner de GitHub Actions**: automatiza que cada push a `main` actualice el código del panel y reinicie el servicio — no toca la tarea programada (esa se registra una sola vez, no cambia con cada deploy).

## Antes de tocar nada: verificar qué ya existe en el server

**Ya hay otras apps corriendo en ese mismo server vía NSSM, Caddy y GitHub Actions.** Todo lo que sigue (nombre de servicio, puerto, entrada de Caddy, carpeta) son sugerencias — hay que confirmarlas contra lo que ya está para no pisar ni reiniciar sin querer un servicio de otro proyecto. Correr esto primero:

```powershell
nssm list                                    # servicios NSSM ya registrados (evitar el mismo nombre)
netstat -ano | findstr LISTENING             # puertos ya en uso (elegir uno libre)
schtasks /query /fo table | findstr /i misrx # confirmar que no exista ya una tarea con ese nombre
Get-ChildItem C:\apps                        # o donde sea que vivan las otras apps, ver la convencion real de carpetas
```

Y revisar el `Caddyfile` existente (`caddy validate` antes de recargar, `caddy reload` en vez de reiniciar el proceso entero) para **agregar** el bloque nuevo sin tocar los bloques de los otros sitios. Si ya hay un runner self-hosted de GitHub Actions registrado en este server (para otros repos), la Sección 7 sigue aplicando igual: cada repo necesita su propio registro de runner (uno registrado en el repo de otro proyecto no toma jobs de este), así que no debería haber conflicto, pero conviene confirmarlo con `Get-Service | findstr actions` antes de instalar uno nuevo.

## Bootstrap inicial (una sola vez, a mano)

Asumiendo que se clona en `C:\apps\gmmisrx` — **ajustar la ruta a la convención real que ya usan las otras apps del server**, confirmada en el paso anterior.

### 1. Clonar y preparar el entorno

```powershell
cd C:\apps
git clone https://github.com/sixtyrc/gmmisrx.git
cd gmmisrx
git checkout main    # o dev, segun corresponda al momento del deploy

cd filter_app
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
```

### 2. Crear el `.env` real

Copiar `.env.example` (en la raíz del repo) a `.env` y completar todos los valores reales (Postgres de GX, Postgres propio, MisRx, Resend, OpenWA, `ADMIN_USERNAME`/`ADMIN_PASSWORD`, y `ALLOWED_HOSTS` con el subdominio real ya creado en Cloudflare: `misrxgm.ctsoft.com.ar`).

### 3. Migrar y crear los usuarios iniciales

```powershell
cd C:\apps\gmmisrx\filter_app
.\venv\Scripts\python manage.py migrate
.\venv\Scripts\python manage.py crear_usuarios_iniciales
```

### 4. Registrar el servicio NSSM del panel web

```powershell
nssm install gmmisrx-panel "C:\apps\gmmisrx\filter_app\venv\Scripts\waitress-serve.exe"
nssm set gmmisrx-panel AppParameters "--port=8010 filter_project.wsgi:application"
nssm set gmmisrx-panel AppDirectory "C:\apps\gmmisrx\filter_app"
nssm set gmmisrx-panel AppStdout "C:\apps\gmmisrx\logs\panel_stdout.log"
nssm set gmmisrx-panel AppStderr "C:\apps\gmmisrx\logs\panel_stderr.log"
nssm start gmmisrx-panel
```

Ajustar el puerto (`8010`) si ya está en uso por otra app.

### 5. Caddy (reverse proxy)

Subdominio ya creado en Cloudflare: `misrxgm.ctsoft.com.ar` (apuntando a este server). **Agregar** (no reemplazar nada existente) al `Caddyfile`:

```
misrxgm.ctsoft.com.ar {
    reverse_proxy localhost:8010
}
```

Validar antes de aplicar (`caddy validate --config <ruta-al-Caddyfile>`) y recargar sin bajar el proceso (`caddy reload`), para no afectar los demás sitios que ya sirve ese mismo Caddy.

### 6. Tarea programada diaria

Ya documentada en `docs/TASK-002_AUTOMATIZACION_PADRON_MISRX.md`:

```powershell
schtasks /create /tn "MisRx - Actualizar Padron Diario" ^
  /tr "\"C:\apps\gmmisrx\scripts\run_actualizar_padron.bat\"" ^
  /sc daily /st 15:30 /ru SYSTEM /rl HIGHEST /f
```

### 7. Runner self-hosted de GitHub Actions

En el repo de GitHub: **Settings → Actions → Runners → New self-hosted runner** (elegir Windows), y seguir las instrucciones que da GitHub ahí (descarga un paquete con un token temporal, distinto cada vez que se genera la pantalla — no se documenta acá porque expira). En resumen, en el server:

```powershell
mkdir C:\actions-runner ; cd C:\actions-runner
# Descargar el paquete que indique GitHub (Settings > Actions > Runners > New self-hosted runner)
.\config.cmd --url https://github.com/sixtyrc/gmmisrx --token <TOKEN_QUE_DA_GITHUB>
.\run.cmd
```

Para que quede corriendo siempre (no solo mientras esa consola esté abierta), instalarlo como servicio de Windows:

```powershell
.\svc install
.\svc start
```

Con esto, el runner queda escuchando jobs de este repo todo el tiempo, como un servicio más del server.

## Despliegues siguientes (automáticos)

Con el runner instalado, cada `push` a `main` dispara `.github/workflows/deploy.yml`, que:
1. Hace `git fetch` + `git reset --hard origin/main` en `C:\apps\gmmisrx` (sin tocar `.env`, `logs/`, `padron_archivos/` — están en `.gitignore`, `git reset --hard` no los toca).
2. Reinstala dependencias (`pip install -r requirements.txt`).
3. Corre `migrate`.
4. Reinicia el servicio NSSM (`nssm restart gmmisrx-panel`).

También se puede disparar a mano desde GitHub (pestaña Actions → el workflow → "Run workflow"), sin esperar un push.

**Importante**: como `main` "no se toca hasta nuevo aviso" (ver `docs/TASK-002...`), este workflow queda armado y listo pero no se va a disparar hasta el día que se decida mergear `dev` → `main`. Se puede probar antes con "Run workflow" manual apuntando a `dev` si hace falta validar el pipeline de deploy en sí, ajustando el `ref` en el dispatch.

## Rollback

Si un deploy rompe algo:

```powershell
cd C:\apps\gmmisrx
git log --oneline -5          # identificar el commit bueno anterior
git reset --hard <commit_bueno>
cd filter_app
.\venv\Scripts\pip install -r requirements.txt
.\venv\Scripts\python manage.py migrate
nssm restart gmmisrx-panel
```

O simplemente volver a correr el workflow contra un commit anterior de `main` (`workflow_dispatch` con ese `ref`).

## Notas de seguridad

- El runner tiene acceso de escritura al filesystem del server — es equivalente a darle a GitHub Actions las mismas capacidades que un admin local. Mantenerlo solo con acceso a este repo (no compartido entre proyectos sin pensarlo).
- El `.env` real vive solo en el server, nunca en el repo ni en los logs del workflow.
- Cambios en el `Caddyfile`/certificados HTTPS quedan fuera del alcance del workflow (son de infraestructura, no de código de la app) — se tocan a mano si hace falta.
