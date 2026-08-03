# TASK-002_AUTOMATIZACION_PADRON_MISRX: Plan de automatización de actualización del padrón

> Estado: **EN IMPLEMENTACIÓN.** Este documento se actualiza a medida que se completa cada fase. Vive en la rama `dev` (no se toca `main` hasta nuevo aviso).

## Estado de implementación (ir tildando a medida que se avanza)

- [x] Query SQL final validada contra la base real de GX (`DISTINCT ON (IndividuoId) ORDER BY AfiliadoFechaAlta DESC`, filtro `AfiliadoConvenio = ANY(convenios_validos)`) — 1181 filas, incluye los 12 casos de excepción automáticamente, resuelve el duplicado de Facundo Altamirano.
- [x] Usuario Postgres de solo lectura (`misrx_padron_ro`) creado y probado (solo `Afiliado`/`Individuo`/`Plan`, confirmado que no puede escribir).
- [x] Base propia de la app creada y probada, local (`misrx_padron_app` en Postgres local, usuario `avicola`) y en el server de producción (`186.125.169.77`, usuario `misrx_padron_app`, lectura/escritura confirmada).
- [x] Encoding UTF-8 validado de punta a punta (Ñ, Ü) entre Postgres GX → Python → base propia — sin mojibake.
- [x] Credenciales MisRx (Basic Auth + `convenio_id=938`) probadas contra `GET /padrones/registros/{convenio_id}` — funcionando.
- [x] Corrección puntual del 2026-08-03 ya subida a MisRx (`AfiliadoGM_Ospena_20260803_104755_CORREGIDO.csv`, 1175 registros, 12 altas, procesado correctamente por MisRx).
- [x] App Django `padron` creada dentro de `filter_app`, con modelos `PadronRun` (historial de corridas), `AfiliadoExcepcion` (casos tratados/pendientes) y `AuditLogEntry` (auditoría de login/acciones). Migraciones corridas contra Postgres local.
- [x] `filter_app` migrado de SQLite a Postgres (via `.env`, mismas credenciales que la base propia).
- [x] Resend (mail vía SMTP, mismo esquema que otros proyectos) configurado y probado (`manage.py test_email`) — tuvo que desactivarse momentáneamente Avast (Mail/Web Shield intercepta TLS con su propio certificado) para validar.
- [x] Pendiente resuelto: DNI duplicado `53394899` (Facundo Altamirano, dos `Nro Afiliado`) — la query final lo resuelve sola (se queda con el de alta más reciente), no requirió acción manual.
- [x] Pipeline completo (`manage.py actualizar_padron [--trigger manual|automatico] [--dry-run]`): consulta GX → genera CSV (mismo formato exacto que GeneXus, incluido el detalle real de que la fecha usa guiones y no barras como decía el código fuente) → sube a MisRx → verifica estado → notifica por mail → registra en `PadronRun` con diff de altas/bajas contra la corrida anterior. Probado end-to-end contra producción: MisRx confirmó "Padron procesado correctamente".
- [x] Tarea programada: `scripts/run_actualizar_padron.bat` (activa el venv, corre `actualizar_padron --trigger automatico`, loguea a `logs/actualizar_padron.log`) probado localmente end-to-end. Falta registrar la tarea en el Programador de Tareas de Windows **del server** cuando se despliegue ahí (ver sección de abajo).
- [ ] Falta: panel operativo (vistas Django con login, botón "ejecutar ahora", listado de historial) — estilo visual de referencia: login de GM Salud (logo + tarjeta centrada), adaptado a "MisRx".
- [ ] Falta: WhatsApp (OpenWA) para notificaciones.
- [ ] Falta: despliegue real de la app al server (hoy se desarrolla y prueba en local, contra las bases remotas).

## Objetivo

Reemplazar el proceso 100% manual actual (bajar 2 archivos de la app GeneXus a mano, cruzarlos con `filter_app`, subir el resultado a mano a la web de MisRx) por un proceso automático diario, con:
- Un panel operativo simple para disparar el proceso a mano cuando haga falta.
- Login y auditoría de accesos/acciones.
- Notificación de resultado (mail + WhatsApp).

## Contexto de negocio (por qué existe este problema)

- El sistema GeneXus (Ospena/GM) maneja afiliados de 2 convenios: `OSFOT` (código `FOT`) y `Ospena/NAV` (código `NAV`).
- OSFOT se dio de baja con el proveedor de recetas digitales anterior ("la generadora"). Hoy a MisRx solo deben mandarse los afiliados **vigentes de Ospena (NAV)**.
- El reporte GeneXus que arma el CSV para MisRx (`WPMisRxAfiliadosExportCSV4`, ver más abajo) **no filtra por convenio** — trae todos los convenios mezclados. Por eso hoy hace falta un cruce manual: se baja aparte un Excel de "afiliados de OSFOT" (desde la pantalla general de Afiliados) y se excluyen esos DNI del CSV.
- GeneXus no se puede modificar (sin licencia), así que la corrección tiene que hacerse fuera de GeneXus.

## Análisis del proyecto actual (`filter_app`)

App Django local, sin autenticación, sin base de datos real, un único flujo (`filter_app/processor/views.py`):
1. Recibe un Excel (afiliados a excluir, columna `DNI`) y un CSV (padrón maestro, columna `Nro Documento`, separador `;`).
2. Cruza por DNI, genera `AfiliadoGM_Ospena_YYYYMMDD_HHMMSS.csv` sin las coincidencias, más un reporte de "no encontrados".
3. Todo manual: se descarga y se sube a mano a la web de MisRx.

Corre localmente (`start.bat` / `scripts/run_filter_app.ps1`), sin login, sin persistencia de historial de corridas.

## Análisis de la API MisRx

Spec real (Swagger 2.0) en `https://www.misvalidaciones.com.ar/static/mvrest.json`. Todo bajo **Basic Auth**.

| Endpoint | Uso |
|---|---|
| `POST /padrones/cargar/{convenio_id}` | Sube el padrón (`multipart/form-data`, campo `archivo`, CSV/TXT). Responde `{success, data:[...]}`. **Siempre padrón completo**, no incremental (confirmado). |
| `GET /padrones/registros/{convenio_id}` | Historial de cargas con estado de procesamiento (`padrones_procesa_estado_id/descripcion`) — sirve para confirmar que una carga fue *procesada*, no solo *recibida*. |
| `GET /consultas/disponibles` + `POST /consultas/consultar/{consulta_id}` | Motor de consultas genéricas habilitadas por MisRx (no usado hoy, candidato a futuro). |
| `GET /receta/{convenio_id}` y variantes | Consulta de recetas validadas por período/afiliado/DNI (no usado hoy, candidato a futuro para conciliar consumos). |

## Reconstrucción de la lógica de origen (GeneXus → SQL directo)

Se analizaron los exports de KB (`gx/afiliado.xpz`, `gx/reportecsv.xpz`) para reconstruir la query exacta que arma el CSV hoy, con el objetivo de reemplazar la descarga manual por una consulta directa a la Postgres de GeneXus (usuario de **solo lectura**), agregando el filtro de convenio que hoy falta.

Objeto GeneXus real: Procedure `WPMisRxAfiliadosExportCSV4` (dentro de `afiliado.xml`), sub `WriteData`. Filtro fijo hoy: `AfiliadoEstado = 'ACT' AND AfiliadoBaja = 'N'`, sin convenio.

**Query propuesta (a confirmar nombres físicos reales de columnas contra la base, ya probada informalmente en pgAdmin con éxito):**

```sql
WITH afiliado_vigente AS (
    -- Por cada persona (IndividuoId), se queda con el registro de Afiliado
    -- MAS RECIENTE por fecha de alta. Esto resuelve el caso de personas con
    -- un registro viejo en un convenio (ej. OSFOT) y uno nuevo en otro (NAV):
    -- gana el mas reciente, sin importar si el viejo tambien estaba activo.
    SELECT DISTINCT ON (a.IndividuoId)
        a.AfiliadoId, a.IndividuoId, a.PlanId,
        a.AfiliadoEstado, a.AfiliadoConvenio, a.AfiliadoBaja,
        a.AfiliadoFechaAlta, a.AfiliadoPMI, a.AfiliadoOncologico
    FROM Afiliado a
    ORDER BY a.IndividuoId, a.AfiliadoFechaAlta DESC
)
SELECT
    i.IndividuoDNI,
    v.AfiliadoId,
    i.IndividuoNombre,
    i.IndividuoApellido,
    i.IndividuoSexo,
    i.IndividuoFecNac,
    v.AfiliadoPMI,
    v.AfiliadoOncologico,
    p.PlanCodigoMisrx,
    p.PlanDescripcion
FROM afiliado_vigente v
JOIN Individuo i ON i.IndividuoId = v.IndividuoId
JOIN Plan p       ON p.PlanId = v.PlanId
WHERE v.AfiliadoEstado = 'ACT'
  AND v.AfiliadoBaja = 'N'
  AND v.AfiliadoConvenio = ANY(:convenios_validos)   -- ['NAV'] hoy, PARAMETRIZABLE (lista en config/.env), no hardcodear
```

`AfiliadoConvenio` es atributo propio y directo de `Afiliado` (dominio `Convenios`, 3 caracteres: `FOT`=OSFOT, `NAV`=OSPENA) — no requiere joins extra. `:convenios_validos` es una lista parametrizable (hoy solo `NAV`; `FOT` es el que hay que excluir) para poder sumar/cambiar convenios sin tocar código. La regla "me quedo con el alta más reciente por persona" reemplaza cualquier necesidad de cruce manual por DNI contra otro convenio: si alguien tiene alta vieja en OSFOT y alta nueva en NAV, automáticamente prevalece la de NAV.

### Formato de salida a replicar exactamente (mismo separador/orden/transformación que genera GeneXus hoy)

Separador `;`, con header. Columnas en orden:

| # | Header | Columna origen | Transformación |
|---|---|---|---|
| 1 | Nro Documento | `IndividuoDNI` | tal cual |
| 2 | Nro Afiliado | `AfiliadoId` | tal cual |
| 3 | Nombres | `IndividuoNombre` | `;`→`,` + sanitización (función interna GX no verificable 100% desde el export) |
| 4 | Apellido | `IndividuoApellido` | igual que Nombres |
| 5 | Sexo | `IndividuoSexo` | `F→Femenino`, `M→Masculino`, `O→Otro`, otro valor→vacío |
| 6 | Fecha Nacimiento | `IndividuoFecNac` | formato `yyyy/mm/dd` |
| 7 | PMI | `AfiliadoPMI` | `Si→'1'`, resto→`'0'` |
| 8 | Oncologico | `AfiliadoOncologico` | `Si→'1'`, resto→`'0'` |
| 9 | PlanCodigo | `PlanCodigoMisrx` | tal cual |
| 10 | Plan | `PlanDescripcion` | `;`→`,` + sanitización |

**Pendiente de validar con un archivo real antes de confiar 100%:** posible bug de truncado en el primer header (`.Substring(2)` sobre un separador de 1 char) y el encoding real del archivo (no está fijado en el código GX). Se resuelve comparando byte a byte contra un CSV bajado a mano.

## Validación hecha contra datos reales (2026-08-03)

Se cruzaron archivos reales bajados ese día (`AfiliadoWWExport-787.xlsx` = afiliados OSFOT, `WPMisRxAfiliadosExportCSV (8).csv` = padrón sin filtrar, `MisRxAfiliados.csv` = padrón actual del lado MisRx) para comparar el proceso manual actual contra el enfoque de query directa por convenio.

| Métrica | Valor |
|---|---|
| DNIs únicos a excluir (OSFOT) | 2893 |
| Registros en CSV (todos los convenios, ACT+no-baja) | 2256 |
| Eliminados por cruce manual (DNI) | 1093 |
| **Restantes (proceso manual actual)** | **1163** |
| Consulta SQL directa (`convenio='NAV'`), corrida el mismo día | **1181** |
| DNIs activos hoy en MisRx (`MisRxAfiliados.csv`) | 1167 |

### Hallazgo: el proceso manual actual excluye por error afiliados activos de NAV

Se identificaron **12 personas** cuyo único registro en OSFOT figura como `Baja` (nunca `Activo`), pero que sí aparecen en el CSV filtrado por `ACT` — es decir, tienen un registro **activo en NAV** aparte del viejo registro de OSFOT. El cruce por DNI las excluye igual, porque no distingue de qué convenio viene la coincidencia.

Se confirmó contra `MisRxAfiliados.csv`: **las 12 figuran `Inactivo` en MisRx ahora mismo**, sin excepción — nunca se cargaron activas por este mismo problema. Esto no es un caso aislado de hoy: es un problema sistémico del método "excluir por DNI cruzando con otro convenio", que la query directa por `AfiliadoConvenio='NAV'` no tiene (filtra por el convenio del registro real, no por coincidencia de un identificador que puede repetirse entre convenios).

Lista de las 12 personas (DNI): `30571805, 35037263, 40031628, 40501665, 41355695, 53228021, 57199786, 57435309, 58629764, 59147919, 70176606, 70450371`. Reportes completos (con nombres) guardados localmente en `gx/reporte_sospechosos_*.csv` — **no versionados en git** (contienen DNI/nombres reales).

**Conclusión: la query directa por convenio no es solo más simple de automatizar, es más correcta que el proceso manual vigente.**

### Corrección aplicada manualmente (2026-08-03)

El usuario verificó las 12 personas contra el sistema y confirmó que deben estar habilitadas para consumir recetas. Se generó `gx/AfiliadoGM_Ospena_20260803_104755_CORREGIDO.csv` (1163 restantes del cruce de hoy + las 12 excepciones = 1175) para subir manualmente a MisRx y dejar la base al día mientras se implementa el proceso automático. Este archivo no reemplaza el análisis de la causa raíz (ya corregida en el diseño de la query de arriba), es solo el parche puntual del dato ya cargado.

Nota aparte detectada al armar este archivo: el DNI `53394899` (FACUNDO EZEQUIEL ALTAMIRANO) figura duplicado en el CSV de origen de hoy con dos `Nro Afiliado` distintos (`3402` y `1631`), mismo plan — no relacionado a OSFOT/NAV, es un dato preexistente en el reporte de GeneXus. Queda pendiente de decidir (aplicando la misma regla de "alta más reciente" cuando se tenga esa fecha disponible en la query).

## Proceso de verificación y auditoría de excepciones (para que esto no vuelva a pasar desapercibido)

Aunque la query con `DISTINCT ON (IndividuoId) ORDER BY AfiliadoFechaAlta DESC` resuelve el caso general hacia adelante, el proceso automático debe incluir una verificación activa en cada corrida, para detectar inconsistencias entre "lo que el sistema dice que debería estar activo" y "lo que MisRx tiene cargado realmente" — por si aparece un caso nuevo de la misma familia (o cualquier otro tipo de desfasaje).

**Cada corrida debe:**
1. Calcular el padrón vigente (query de arriba).
2. Comparar contra el estado actual reportado por MisRx (activos/inactivos) para detectar diferencias:
   - **Personas que deberían estar activas y no lo están** → caso a informar y corregir (el mismo patrón que las 12 de hoy).
   - **Personas que ya no aparecen en el padrón vigente porque se dieron de baja legítimamente** → esperado, **no es una anomalía**, se registra como baja normal, no se alerta como error.
3. Mantener un registro persistente de excepciones detectadas (tabla simple: DNI, fecha de detección, motivo, fecha de resolución, estado `pendiente`/`tratado`).
   - Un caso ya marcado `tratado` (como estas 12, una vez subidas) **no se vuelve a informar** en corridas futuras, aunque el patrón de causa (alta vieja en otro convenio) sea el mismo — solo se informan casos **nuevos** no vistos antes.
4. Al terminar cada actualización: informar el resultado (mail/WhatsApp) y **dejar registro en una bitácora** (mismo formato que la bitácora de `TASK-001`, o una tabla dedicada) con fecha, totales, y el detalle de excepciones nuevas encontradas/tratadas ese día.

## Infraestructura de despliegue

- Windows Server (VPS), mismo proveedor que aloja la base Postgres de GeneXus (llega en red local/LAN, sin fricción).
- Salida a internet para llamar a la API de MisRx sin problema.
- Ya se usan Caddy (reverse proxy/HTTPS) + NSSM (correr servicios) para otras apps Django/React — mismo patrón a seguir acá **para el panel web** (proceso que queda corriendo).

### Tarea diaria: Task Scheduler, no NSSM

La actualización del padrón es un job que corre, hace su trabajo y termina — no un proceso que deba quedar vivo. Por eso usa el **Programador de Tareas de Windows** (nativo del server), no NSSM (que es para procesos persistentes como el panel web). Son dos mecanismos distintos para dos naturalezas de proceso distintas, conviviendo en el mismo server sin pisarse.

- Script: `scripts/run_actualizar_padron.bat` — activa el venv, corre `manage.py actualizar_padron --trigger automatico`, loguea a `logs/actualizar_padron.log`. Usa `%~dp0` para resolver su propia ubicación, así funciona sin importar en qué carpeta del server quede clonado el repo.
- Horario definido: **todos los días a las 15:30 hora Argentina**.
- Registrar la tarea en el server (ajustar la ruta al path real donde quede el repo ahí, y confirmar que la zona horaria del Windows del server sea Argentina — si no, ajustar el horario acorde):

```
schtasks /create /tn "MisRx - Actualizar Padron Diario" ^
  /tr "\"C:\ruta\al\repo\scripts\run_actualizar_padron.bat\"" ^
  /sc daily /st 15:30 /ru SYSTEM /rl HIGHEST /f
```

- Probado localmente end-to-end (`.bat` completo, incluida la subida real a MisRx) — funciona. Falta solamente registrarlo en el server una vez desplegado ahí.

## Diseño propuesto

### 1. Origen de datos (reemplaza la descarga manual)
- Usuario Postgres de **solo lectura**, restringido idealmente a una vista dedicada (no a las tablas completas) con las columnas necesarias.
- Conexión restringida por IP/firewall a la máquina de la automatización, con `statement_timeout` corto.
- Ejecuta la query de la sección anterior, parametrizada por convenio vía config/`.env` (`CONVENIO_PADRON_MISRX=NAV`).

### 2. Generación del archivo
- Réplica exacta del formato de columnas/transformaciones de la tabla de arriba (separador `;`, header, encoding a confirmar).
- Validado contra un CSV real antes de reemplazar el proceso manual (comparación byte a byte del header/encoding, y de conteos en una corrida en paralelo).

### 3. Subida a MisRx
- `POST /padrones/cargar/{convenio_id}` (Basic Auth, credenciales ya disponibles).
- Verificación posterior con `GET /padrones/registros/{convenio_id}` (no alcanza con "recibido", hay que confirmar "procesado").

### 4. Notificaciones
- Mail + WhatsApp (skill OpenWA ya instalada) en éxito y en error.

### 5. Orquestación
- Script/management command único: consulta → genera archivo → sube → verifica → notifica.
- Tarea diaria (NSSM/Task Scheduler), mismo servidor que aloja la app.
- `filter_app` (el flujo manual actual) queda como respaldo, no se elimina.

### 6. Panel operativo (nuevo alcance, pedido por el usuario)
- Botón "Ejecutar ahora" para correr el pipeline completo bajo demanda, con confirmación antes de disparar (acción real sobre producción).
- Historial de corridas (automáticas y manuales) con las mismas estadísticas que ya muestra `filter_app` hoy (totales, resultado de MisRx, estado de procesamiento) — requiere persistir en base de datos (hoy la app es stateless).
- Quién disparó cada corrida.

### 7. Login y auditoría (nuevo alcance, pedido por el usuario)
- Autenticación real (Django auth) — hoy no existe, cualquiera con acceso a la URL puede correr el proceso.
- Auditoría de intentos de login (éxito/fallo) y de cada acción de "ejecutar ahora" (usuario + timestamp).
- Protección contra fuerza bruta en el login (throttling/lockout).

### 8. Seguridad (transversal)
- HTTPS vía Caddy, `DEBUG=False`, `SECRET_KEY` real por variable de entorno (hoy usa la de desarrollo de Django), cookies de sesión/CSRF `Secure`.
- Todas las credenciales (Postgres, MisRx, SMTP, WhatsApp) en `.env`, nunca en código ni en git.
- Rol de Postgres de solo lectura, mínimo privilegio (idealmente solo sobre una vista dedicada).
- Evaluar restricción adicional de red (IP allowlist en Caddy o VPN) dado que son pocos usuarios reales.
- Nunca loguear el padrón completo (DNI/nombres) en texto plano en logs de auditoría — solo metadatos de la corrida.

## Pendientes antes de implementar

1. Confirmar nombres físicos reales de columnas en Postgres contra la base (ya se probó informalmente con éxito, falta la confirmación formal con el usuario de solo lectura dedicado).
2. Validar header exacto y encoding del CSV real generado por GeneXus (posible bug de truncado del header).
3. Decidir si se corrige el problema de las 12 personas excluidas por error de forma manual (ya) o se resuelve automáticamente al migrar al nuevo proceso.
4. Crear el usuario Postgres de solo lectura (idealmente sobre una vista dedicada, no las tablas completas).
5. Confirmar credenciales/convenio_id de MisRx (ya disponibles según el usuario).

## Estado del repositorio

- Repo: `https://github.com/sixtyrc/gmmisrx`
- `main`: estado inicial (baseline previo a esta automatización), no se toca hasta nuevo aviso.
- `dev`: rama de trabajo activa para todo lo de este documento.
