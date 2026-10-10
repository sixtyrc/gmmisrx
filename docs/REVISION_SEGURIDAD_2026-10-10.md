# Revisión de seguridad externa — 2026-10-10

Escaneo **desde afuera** de `https://misrxgm.ctsoft.com.ar` (pasa por Cloudflare, igual que un atacante real). Herramientas: **OWASP ZAP baseline** (pasivo, no ataca) y **Nuclei** (plantillas de CVEs y configuraciones). Las guías y comandos están en el repo PayePOS, `docs/qa/herramientas-seguridad.md`.

## Resultado

- **ZAP baseline:** 0 fallas, 56 reglas aprobadas, 11 avisos.
- **Nuclei:** la primera corrida no arrancó (no pudo bajar las plantillas) y se relanzó el 2026-10-10. **Sin resultado anotado todavía**: completar acá cuando termine.

## Hallazgos y qué se hizo

| Aviso de ZAP | Qué es | Decisión |
|---|---|---|
| Cookie Without Secure Flag | Las cookies de sesión y de CSRF no llevaban `Secure`: podían viajar por una conexión sin HTTPS. | **Corregido** en `filter_app/filter_project/settings.py` (commit `cd89d68`): `SESSION_COOKIE_SECURE` y `CSRF_COOKIE_SECURE` valen `not DEBUG`. En local con `DEBUG=True` siguen funcionando por HTTP. |
| Cookie No HttpOnly Flag | Es la cookie `csrftoken`. Django la deja legible a propósito (el doble envío de CSRF la necesita). | **No se cambia.** Poner `CSRF_COOKIE_HTTPONLY=True` puede romper formularios. La cookie de sesión ya es `HttpOnly` por defecto. |
| User Controllable HTML Element Attribute (XSS) | El parámetro `?next=` del login se refleja en un `<input hidden>`. | **Falso positivo.** `padron/templates/padron/login.html` lo imprime con `{{ next }}`, que Django escapa solo, y `LoginView` valida adónde redirige. |
| CSP y Permissions-Policy no definidas | Faltan esas cabeceras. | **Pendiente.** Una CSP depende de lo que cargan las plantillas (scripts y estilos incrustados) y mal puesta deja pantallas en blanco. Se arma aparte, empezando con `Content-Security-Policy-Report-Only`. |
| Sub Resource Integrity, COEP, "Modern Web Application", cache | Ruido normal o informativo. | Sin acción. |

## Pendiente de desplegar

1. Hacer el deploy normal (merge `dev` → `prod` y push de `prod`, ver `DEPLOY.md`). Hasta entonces el servidor sigue con las cookies sin `Secure`.
2. **Verificar en el `.env` real del servidor** (no se puede ver desde el repo):
   - `DJANGO_DEBUG=False`. El valor por defecto del código es `True`. En producción hoy está apagado (la página 404 es la normal, no la de depuración), pero conviene tenerlo escrito.
   - `DJANGO_SECRET_KEY` definida. Si falta, Django usa la clave insegura de `settings.py`.
3. Después del deploy, comprobar que las cookies salen con `Secure`:

```
curl -sI https://misrxgm.ctsoft.com.ar/padron/login/ | findstr /i set-cookie
```

Cada línea `Set-Cookie` debe incluir `Secure`.

## Qué no se probó

Este escaneo es de superficie, sin sesión iniciada: no revisa permisos por rol ni la lógica interna del panel. Para eso hace falta una prueba activa en un entorno local, no en producción.
