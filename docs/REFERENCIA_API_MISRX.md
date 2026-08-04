# Referencia: API REST de MisValidaciones (MisRx)

Catálogo completo de los endpoints publicados por MisRx (proveedor de recetas digitales / validación de recetas), con qué hace cada uno, cómo se usa y para qué podría servir en la integración con GM Salud.

**Fuente:** spec Swagger 2.0 real, bajada directamente del servidor el 2026-08-04 desde `https://www.misvalidaciones.com.ar/static/mvrest.json` (la Swagger UI de `https://www.misvalidaciones.com.ar/static/rest_api/#/` renderiza este mismo JSON). Es la fuente de verdad — ante cualquier duda, volver a bajar ese archivo, puede haber cambiado.

Este documento arrancó como solo **investigación** (qué existe y para qué serviría), pero ya deriva en una implementación real: [[proyecto-automatizacion-padron-misrx]] usa `POST /padrones/cargar/{convenio_id}` y `GET /padrones/registros/{convenio_id}` para el padrón (ver `filter_app/padron/services/misrx_client.py`), y desde el 2026-08-04 también `GET`/`POST /prescripcion/{convenio_id}` para el circuito de crónicos, vía la pantalla `/padron/cronicos/` (ver sección 4).

---

## 1. Datos generales

| | |
|---|---|
| **Base URL** | `https://www.misvalidaciones.com.ar/` |
| **Autenticación** | HTTP Basic Auth en **todos** los endpoints (usuario/clave que ya tenemos en `.env` como `MISRX_USER`/`MISRX_PASSWORD`) |
| **Formato** | JSON (`application/json`), salvo carga de padrón (`multipart/form-data`) y el cupón PDF |
| **`convenio_id`** | Identificador numérico del convenio/obra social dentro de MisRx. El nuestro (Ospena/NAV) es `938` (confirmado en `TASK-002`, variable `MISRX_CONVENIO_ID`) |
| **Códigos de convenio GX (`AfiliadoConvenio`)** | Internamente GX usa los códigos cortos `FOT` y `NAV`. Para el operador se muestran como **OSFOT** y **OSPENA** respectivamente (nombres reales de las obras sociales, no los códigos internos) — mapeo centralizado en `filter_app/padron/services/convenios.py` (`nombre_convenio()`) y filtro de template `nombre_convenio` (`{% load padron_extras %}`). Usar siempre este helper en vez de mostrar el código crudo en cualquier pantalla/reporte nuevo. |
| **`clave_id`** | Un segundo identificador de cliente que exigen varios endpoints además del Basic Auth — no lo tenemos configurado hoy, habría que pedírselo a MisRx/Preserfar si se quiere usar algo de la sección "Recetas" |
| **Soporte** | Preserfar — soporte@preserfar.com |

Los endpoints se agrupan en 6 áreas: **Recetas** (validación tradicional), **Recetas digitales** (consulta, no emiten), **Prescripciones** (tratamientos crónicos/prolongados), **Patologías**, **Autorizaciones** y **Padrones** (la que ya usamos), más un motor genérico de **Consultas**.

---

## 2. Recetas (validación de recetas en farmacia)

Esta es la función núcleo de MisRx: una farmacia valida (autoriza el descuento de) una receta física contra el convenio. GM Salud normalmente no sería quien llama a estos endpoints (eso lo hace el sistema de la farmacia o el punto de venta), pero **sí son útiles para auditar/conciliar** qué se validó contra afiliados de Ospena.

### `GET /receta`
- **Qué hace:** consulta el detalle de una receta ya validada, dado su código de validación.
- **Parámetros:** `clave_id` (query, requerido), `cod_validacion` (query, requerido).
- **Respuesta:** objeto `receta` — estado, convenio, farmacia (CUF/GLN), datos del afiliado, médico, ítems validados con nombre de producto/troquel/cantidad/cobertura/precio.
- **Utilidad:** ver el detalle completo de una validación puntual (ej. responder un reclamo de un afiliado o farmacia sobre una receta específica).

### `POST /receta`
- **Qué hace:** valida una receta física nueva (la llamaría el software de la farmacia, no GM Salud).
- **Parámetros:** `clave_id`, `cuf` (CUF/GLN de la farmacia, opcional), body `newReceta`.
- **Body `newReceta` (campos requeridos):** `convenio`, `nro_recetario`, `afiliado_documento`, `afiliado_credencial`, `medico_tipo_mat`, `medico_nro_mat`, `medico_nombres`, `fecha_receta` (yyyy-mm-dd), `items[]` (cada ítem: `nro_item`, `cantidad`, `troquel`, `codbarras`, opcional `precio_unitario`, `porc_cobertura`). Opcionales: datos del afiliado (nombre, sexo, fecha nacimiento, plan), auditor, `token_otp`, `factura_nro`.
- **Respuesta:** `receta` con `cod_validacion`, estado y detalle por ítem (aprobado/rechazado, cobertura, importes).
- **Utilidad para GM Salud:** no aplica salvo que GM Salud quisiera construir su propio front de farmacia — no es el caso hoy.

### `DELETE /receta`
- **Qué hace:** anula una receta ya validada.
- **Parámetros:** `clave_id`, `cuf` (opcional), `cod_validacion` (requerido).
- **Respuesta:** 204 sin contenido, o error.
- **Utilidad:** revertir una validación errónea. Uso operativo de farmacia, no de GM Salud.

### `POST /receta/registra_factura`
- **Qué hace:** asocia datos de facturación (CUIT, tipo/punto/número de comprobante, importe, fecha) a una validación previa.
- **Parámetros:** `clave_id`, `cuf` (opcional), `cod_validacion` (requerido), body `facturadatos` (opcional — JSON estándar o el QR de factura en base64).
- **Respuesta:** `registrofactura` — estado `A` (autorizado) o `R` (rechazado) + lista de errores.
- **Utilidad:** cierre del circuito de facturación entre farmacia y obra social. No es un caso de uso de GM Salud como tal.

### `GET /receta/{convenio_id}`
- **Qué hace:** **lista** las recetas validadas del convenio en un rango de fechas, con muchos filtros (por DNI, plan, farmacia, N° de recetario, credencial, código de validación, código de presentación).
- **Parámetros:** `convenio_id` (path), `clave_id`, `desde` (requerido), `hasta` (opcional, default hoy), y filtros opcionales: `plan_id`, `dni`, `nroafiliado`, `codvalidacion`, `codigo_presentacion`, `cuf`, `nrorecetario`, `credencial`.
- **Respuesta:** `listado_recetas` — `total` + array `recetafull` (cada una con farmacia, médico, ítems con precios/cobertura/troquel).
- **Utilidad — la más relevante de esta sección para GM Salud:** es el endpoint para **traer el consumo de recetas del período** (por DNI o global) y cruzarlo contra el padrón. Sirve para: reportes de consumo por afiliado, detección de afiliados que consumen sin figurar activos en el padrón, conciliación de facturación con farmacias, o alimentar un dashboard de "recetas validadas este mes" en el panel `/padron/`.

---

## 3. Recetas digitales (prescripción electrónica — solo consulta)

Recetas emitidas digitalmente (no en papel), asociadas a autorizaciones/tratamientos. Acá GM Salud sería consultante, no emisor — la emisión la hace el médico/prestador desde otro sistema.

### `GET /receta/digitales/{convenio_id}`
- **Qué hace:** lista recetas digitales/prescripciones del convenio en un período, con filtros ricos (DNI/CUIL, credencial, médico, estado, token, texto libre por nombre de afiliado).
- **Parámetros:** `convenio_id` (path), `clave_id`, `fecha_receta_desde`/`fecha_receta_hasta` (ambos requeridos), y opcionales: `plan_id`, `afiliado_dni_cuil`, `afiliado_credencial`, `medico_dni_cuil`, `recetas_estado_id`, `token`, `nrorecetario`, `filtro` (texto).
- **Respuesta:** `listado_recetas_digitales` — cada receta trae diagnóstico, CIE-10, si es tratamiento prolongado, estado, médico, ítems con monodroga/marca/laboratorio/troquel.
- **Utilidad:** buscador de recetas digitales de un afiliado (ej. "¿qué le recetaron a este DNI este mes?") o reporte de diagnósticos/CIE-10 más frecuentes. Requiere `clave_id`, que hoy no tenemos configurado.

### `GET /receta/cupon/{codvalidacion}`
- **Qué hace:** descarga el PDF del cupón de una validación (el comprobante que imprime la farmacia).
- **Parámetros:** `codvalidacion` (path, requerido). *(Nota: este endpoint no declara `security: basicAuth` en el spec, a diferencia de casi todos los demás — a confirmar en la práctica si igual exige Basic Auth.)*
- **Respuesta:** archivo PDF.
- **Utilidad:** reimprimir/reenviar comprobantes a un afiliado o auditoría que perdió el cupón original.

### `POST /receta/adesfa`
- **Qué hace:** procesa mensajes en formato ADESFA (estándar de intercambio entre farmacias/obras sociales/COFA), por ahora solo `codigoAccion 910100`.
- **Parámetros:** `clave_id`, `cuf` (opcional), body con el XML ADESFA como string (comillas simples, sin saltos de línea).
- **Respuesta:** JSON con el XML de respuesta ADESFA.
- **Utilidad:** integración de bajo nivel con sistemas de farmacia que hablan ADESFA en vez de la API JSON nativa. Caso de uso muy específico, poco probable que GM Salud lo necesite.

### `GET /receta/prescripcion/{nrorecetario}/{convenio_id}`
- **Qué hace:** consulta una receta digital/autorización puntual por su número de recetario, identificando al afiliado por DNI o por credencial.
- **Parámetros:** `nrorecetario` (path), `convenio_id` (path), `clave_id`, `afiliado_documento` (requerido, 0 si se usa credencial), `afiliado_credencial` (requerido, blanco si se usa DNI), `cuf` (opcional, para chequear estado en convenio de esa farmacia).
- **Respuesta:** `recetadigital` con estado, datos del afiliado, médico, farmacia (`farmacia_info`: activa/inactiva) e ítems.
- **Utilidad:** lookup puntual "¿está vigente esta receta/autorización?" — útil para un módulo de atención al afiliado o para que la farmacia valide antes de dispensar.

---

## 4. Prescripciones (tratamientos crónicos / consumos periódicos)

Distinto de "receta": una **prescripción** es una autorización de cobertura recurrente (ej. "este afiliado tiene cubierto tal medicamento X unidades por mes durante 6 meses"), contra la cual después se validan recetas individuales.

### `GET /prescripcion/{convenio_id}`
- **Qué hace:** busca prescripciones por número de afiliado y/o por ID de prescripción.
- **Parámetros:** `convenio_id` (path), `nroafiliado` (opcional), `prescripcion_id` (opcional) — se requiere al menos uno de los dos.
- **Respuesta:** `prescripcionesLista` — cada una con monodroga, patología, % cobertura, cantidad/período de consumo permitido, fechas de vigencia, productos asociados.
- **Utilidad:** consultar si un afiliado tiene tratamientos crónicos activos y su cobertura vigente — útil para un módulo de "medicación crónica" en el panel.

### `POST /prescripcion/{convenio_id}`
- **Qué hace:** ABM (alta/baja/modificación) de una prescripción — dar de alta un tratamiento crónico, modificarlo o darlo de baja (`baja` en el body).
- **Parámetros:** `convenio_id` (path), body `prescripcionABM`.
- **Body (requeridos):** `plan_id`, `nro_afiliado`, `nro_dni`, `monodroga_id`, `porc_cobertura`, `consumo_cantidad_por_periodo`, `consumo_periodo_tipo`, `consumo_cantidad_por_receta`, `fecha_inicio`, `fecha_fin`, `productos[]` (cada uno con `producto_id` requerido). Opcionales: `prescripcion_id` (para editar), `patologia_id`, `causa_excepcion_id`, sexo/categoría/CUIL del afiliado.
- **Respuesta:** `abmPrescripcionResult` — `prescripcion_id` + mensaje.
- **Utilidad — potencialmente la más valiosa para expandir el sistema:** si GM Salud gestiona autorizaciones de medicación crónica (oncológicos, diabetes, etc.) hoy por otro medio (papel, mail), esto permitiría cargar/mantener esas autorizaciones directamente vía API en vez de que el afiliado tenga que tramitarlas aparte con MisRx.

#### Confirmado en vivo (2026-08-04): hay 2 prescripciones crónicas reales cargadas hoy en nuestro convenio

Se barrieron los ~3335 números de afiliado del padrón actual (`gx/Afiliados.csv`) contra `GET /prescripcion/938?nroafiliado=...` — **2 tienen una prescripción crónica real cargada** (no son datos de prueba, son afiliados reales, confirmado por el usuario). *(El barrido tuvo ~37% de fallos de conexión por exceso de concurrencia y no se pudo re-verificar al 100% por un bloqueo del entorno a un segundo barrido masivo — hay razonable confianza de que no son solo 2 en base a la muestra que sí completó, pero no está descartado al 100% que haya alguna más.)*

Ejemplo real completo (nro. afiliado 2227):
```json
{
  "afiliado": "LOVATO LUQUE ABDIEL EFRAIN",
  "nro_afiliado": "2227",
  "nro_dni": 55524665,
  "prescripcion_id": 1416307,
  "plan": "Crónicos",
  "plan_id": 1939,
  "porc_cobertura": "100",
  "monodroga_id": 554,
  "monodroga": "risperidona",
  "patologia_id": 0,
  "patologia": null,
  "causa_excepcion_id": 0,
  "productos": [
    {"producto_id": 22207, "consumo_cantidad_representa": 1, "repone": 0, "porc_cobertura": null},
    {"producto_id": 21153, "consumo_cantidad_representa": 1, "repone": 0, "porc_cobertura": null}
  ],
  "consumo_cantidad_por_periodo": 2,
  "consumo_periodo_tipo": "mensual calendario",
  "consumo_cantidad_por_receta": 2,
  "consumo_periodo_dias": 0,
  "fecha_inicio": "2025-04-01T00:00:00",
  "fecha_fin": "2030-04-01T00:00:00",
  "fecha_alta": "2025-04-21T07:29:59",
  "ultimo_cambio": "2025-04-25T07:05:00",
  "afiliados_estado": "Inactivo"
}
```
El segundo (nro. afiliado 2533) tiene la misma estructura: monodroga `valproico, ác.` (`monodroga_id 9066`), `plan_id 1939`, cobertura 100%, vigente hasta 2030.

**Hallazgo importante — `afiliados_estado` sí refleja el estado real:** en ambos casos dice `"Inactivo"`, y **coincide exactamente** con el `Estado` real de esos mismos números de afiliado en el padrón (`gx/Afiliados.csv`). Confirma que el campo es preciso — pero el problema práctico sigue siendo el mismo que en la sección 8bis: solo se completa cuando el afiliado tiene una prescripción crónica cargada, y hoy eso son **2 de ~3335 afiliados** — no sirve como chequeo general de estado.

**Qué se necesitaría para poder dar de alta una prescripción nueva vía `POST`, usando estos 2 registros reales como referencia de mapeo de campos:**
- `plan_id` para el circuito de crónicos de nuestro convenio ya se sabe: **1939** ("Crónicos") — distinto del `plan_id` real de cobertura del afiliado (ej. 1076 "Plan ORO" en el padrón). Es un plan interno de MisRx específico para este circuito, no algo que nosotros configuramos.
- `monodroga_id` y `producto_id`: **no hay ningún endpoint que exponga ese catálogo** (a diferencia de `patologia_id`, que sí tiene `GET /patologias/{convenio_id}` con 649 ítems). Solo conocemos los IDs de las 2 monodrogas ya cargadas (554 = risperidona, 9066 = ácido valproico) porque aparecieron en los registros existentes al consultarlos — para cualquier droga nueva habría que pedirle el catálogo a soporte Preserfar, o inferirlo desde el buscador del portal web (que seguramente sí lo tiene).
- `consumo_periodo_tipo`: el **schema de `POST` lo pide como número** (`integer`), pero el `GET` lo devuelve como **texto** (`"mensual calendario"`) — es un enum codificado que no está documentado en ningún lado. No se puede armar un `POST` a ciegas sin saber qué entero corresponde a "mensual calendario" (u otras opciones de periodicidad) — esto también habría que confirmarlo con soporte, o probarlo con mucho cuidado.

**No se ejecutó ningún `POST` de prueba** — es una acción de escritura sobre producción, ligada a personas reales, y no hay forma de "probarlo en un sandbox": cualquier alta/edición real afecta directamente el registro de cobertura crónica de un afiliado real. Si en algún momento se quiere probar, hace falta decidirlo explícitamente (sobre qué afiliado, con qué datos) — no es algo para automatizar como parte de esta investigación.

#### Pantalla armada (2026-08-04): `/padron/cronicos/`

Se armó una pantalla en el panel (`filter_app/padron/`, solo visible/accesible para superuser mientras el comportamiento de `baja` no esté confirmado) para probar esto de forma controlada:
- Consulta por DNI: resuelve DNI → nro_afiliado contra GX (`gx_query.buscar_afiliado_por_dni`) y trae los crónicos reales desde MisRx (`misrx_client.consultar_cronicos`) — **probado en vivo, funciona** (contra el DNI real 59498119 del caso de prueba).
- Debajo, un `<details>` colapsado por defecto ("Cargar / dar de baja una prescripción crónica") con el formulario del ABM. Solo quedan editables los campos que realmente hay que cargar a mano — `nro_afiliado`, `nro_dni` y `plan_id` quedan en modo lectura (vienen resueltos por la búsqueda de DNI o son fijos para el convenio).
- **Monodroga, patología y producto ya no se cargan escribiendo un ID a mano** (el usuario marcó, con razón, que nadie puede saber esos números de memoria) — son 3 buscadores en vivo (texto → dropdown de resultados → click completa el ID real):
  - **Monodroga y Producto** buscan contra una tabla propia (`VademecumItem`) cargada desde el vademécum Alfabeta de la sección 4 — 21.183 productos, indexada, búsqueda instantánea. Elegir una monodroga filtra automáticamente el buscador de producto a sus presentaciones (igual que el flujo del portal de MisRx).
  - **Patología** busca en vivo contra `GET /patologias/938` (no necesita tabla propia, son solo 649 ítems y ya funciona con Basic Auth).
  - Sección "Actualizar vademécum" (colapsada, en la misma pantalla): permite refrescar la tabla subiendo un `.xlsx` a mano o pegando un link de Google Sheets (se normaliza automáticamente al formato de descarga aunque se pegue el link normal del navegador, no hace falta saber la URL de export). Comando equivalente por consola: `manage.py cargar_vademecum`.

#### Permisos y rollback (2026-08-04)

- **El rol Operador (grupo Django, permiso `padron.can_manage_cronicos`) ya puede operar esta pantalla**, no solo el superuser — migración `0007_operador_permiso_cronicos.py`. La consulta por DNI y el ABM quedan disponibles para Operador.
- **El detalle de la bitácora (tabla "Últimas operaciones" y el historial de actualizaciones del vademécum) es visible solo para admin (superuser)** — un Operador puede operar, pero no ver el historial completo de lo que hicieron otros usuarios.
- **Cada edición/baja sobre una prescripción ya existente guarda un snapshot de "cómo estaba antes" (`CronicoLog.estado_anterior`)**, capturado con un `GET` real a MisRx justo antes de mandar el `POST` — así, si una baja o edición termina siendo un error, hay datos reales para reconstruir el estado original (no solo lo que se mandó, sino lo que había antes de tocarlo).
- **Botón "Deshacer" (rollback real, no solo mostrar el dato) — solo admin**, distinto del permiso general de Operador. Reconstruye el payload exacto a partir de `estado_anterior` (incluida la conversión de `consumo_periodo_tipo` de texto a código 0/1/2, y recorte de fechas ISO a `yyyy-mm-dd`) y lo reenvía con `baja: 0` para restaurar el registro. Probada la reconstrucción del payload contra el caso real conocido (nro. afiliado 2533) — coincide exacto con el original. El envío real del rollback en sí (el `POST` a MisRx) queda para cuando haga falta usarlo de verdad, mismo motivo de siempre (no se pueden disparar escrituras de prueba a producción desde este entorno).

**Regla general para features sensibles de acá en más (pedida explícitamente por el usuario, aplicar en el resto del proyecto):** cuando una acción escribe sobre un sistema externo o datos reales y es difícil de deshacer, guardar siempre — en una tabla local o en el mismo log — los datos necesarios para poder reconstruir un rollback manual o automático, no solo lo que se envió. Y cuando la acción es sensible, dejar la posibilidad de rollback (o al menos el detalle de auditoría) restringida a admin, aunque la acción original esté abierta a más roles.
- Cada intento de alta/baja queda registrado en el modelo `CronicoLog` (quién, cuándo, DNI/nro_afiliado, el payload exacto enviado, el status code y **el body de respuesta crudo completo de MisRx**) — se ve en una tabla al pie de la misma pantalla, para poder ir depurando los gaps sin perder el historial de intentos.
- **El `POST` real (alta/baja) todavía no se probó** — el entorno de este asistente bloquea llamados de escritura directos a APIs externas de producción; queda para que el usuario lo dispare manualmente desde el navegador. Valores sugeridos para la primera prueba de `baja` (usando el registro real de nro. afiliado 2533, hoy Inactivo): `prescripcion_id=1418528`, `nro_afiliado=2533`, `nro_dni=59498119`, `plan_id=1939`, `monodroga_id=9066`, `porc_cobertura=100`, `consumo_cantidad_por_periodo=6`, `consumo_periodo_tipo=mensual calendario`, `consumo_cantidad_por_receta=4`, `fecha_inicio=2025-04-01`, `fecha_fin=2030-12-01`, `producto_id=761200013`, tildar "Dar de baja".
- **Guardrail agregado tras probar la pantalla:** el estado GX se muestra en rojo cuando el afiliado no está Activo, y el servidor **bloquea cualquier alta/edición** (no solo lo avisa) si `AfiliadoEstado != 'ACT'` o `AfiliadoBaja != 'N'` — mismo criterio que ya usa `gx_query.obtener_padron_vigente` para el padrón real. La baja de un registro ya existente sigue permitida aunque el afiliado esté inactivo (es justamente el caso de prueba de hoy). *(Bug real encontrado y corregido en el camino: la primera versión comparaba el estado contra el string `"Activo"`, pero GX usa códigos — `ACT`/`BAJA`/`PEND` — así que esa primera versión bloqueaba a todo el mundo, activos incluidos.)*
- **Manual oficial del proceso manual (PDF que aportó el usuario: "MisValidaciones - Obra Social - Carga Prescripciones (cronicidades)", en `gx/`), confirma la arquitectura real de este circuito en el portal:**
  1. Primero hay que asignarle al afiliado un **"Plan Especial"** preconfigurado (ej. "Diabéticos 100% (Mutual)" en el ejemplo genérico del PDF; en nuestro convenio ya sabemos que es "Crónicos", `plan_id 1939`) — esto se hace desde "Gestión de Afiliados" → editar afiliado → "Agregar Plan". No es algo que se arma al vuelo vía API: son planes que MisRx/el administrador del convenio configuran de antemano.
  2. Recién dentro de ese plan asignado se cargan las **prescripciones**: el campo "Monodroga" tiene autocompletado por nombre a partir de 5 caracteres (ej. "insul" → insulina, insulina aspártica, insulina glargina...).
  3. Los **productos** (`producto_id`) se eligen después, de una grilla de presentaciones comerciales de esa molécula (laboratorio, troquel, código de barras, presentación, potencia), filtrable por "VDMs Convenio" / "VDM Plan" / "Manual Farmacéutico completo".
  4. El campo "Periodo" en el portal es **tipo + cantidad** (ej. "plazo días" + `25`, o "plazo mensual") — mapea a `consumo_periodo_tipo` + `consumo_periodo_dias`.
  5. *(Nota que ya no aplica como bloqueante, ver más abajo: en su momento se pensó que el buscador de monodroga/producto del portal era la única fuente posible — se encontró una alternativa completa, ver "RESUELTO" más abajo.)*

- **Documentación oficial de MisRx/Preserfar para el ABM de prescripciones (texto que aportó el usuario, más precisa que el swagger público) — resuelve los gaps que quedaban abiertos:**
  - **`monodroga_id` y `producto_id` son códigos Alfabeta** — el sistema estándar de codificación farmacéutica de Argentina (el mismo que usan la mayoría de los sistemas de farmacia/obra social), no un catálogo propietario de MisRx. Esto es clave: si en algún momento se consigue acceso a Alfabeta (suscripción/API propia), se podrían resolver estos códigos sin depender del buscador del portal de MisRx.
  - **`consumo_periodo_tipo` (el enum que faltaba): `0` = en días, `1` = mensual, `2` = anual.** Nuestro registro real de prueba (nro. afiliado 2533, "mensual calendario" en el `GET`) corresponde a `1`.
  - El campo correcto para identificar una prescripción existente al editar/dar de baja es **`prescripciones_id`** (plural) — el swagger público lo documentaba como `prescripcion_id` (singular), otro bug del spec público que ya tenía varios (ver secciones anteriores). **Ya corregido en la pantalla `/padron/cronicos/`.**
  - `producto.consumo_cantidad_representa`: por defecto toma el número de unidades que indica Alfabeta en la presentación (ej. una caja de 5 ampollas = 5).
  - `producto.porc_cobertura`: opcional, si se deja en 0 no se considera (usa el de la prescripción).
  - `causa_excepcion_id`: igual que `patologia_id`, referencia a una tabla interna de MisRx — pero a diferencia de patologías, **no hay endpoint público para ese catálogo** (pendiente si se necesita).

- **Confirmado en vivo (2026-08-04): los endpoints de búsqueda que usa el portal existen y son alcanzables, pero están protegidos por sesión web, no por Basic Auth** — mismo patrón que `/afiliados/{convenio_id}` (sección 8bis):
  - `GET /monodrogas` → `200 {"success": false, "error": "Session Invalida"}` (con las credenciales Basic Auth de la API — las ignora, pide sesión de portal).
  - `POST /productos` → mismo resultado, mismo mensaje.
  - Esto **confirma exactamente dónde vive el buscador** que se ve en las capturas del portal — ya no es una incógnita de "a ver si existe", es un pedido puntual y concreto para hacerle a soporte: *"¿pueden habilitar `/monodrogas` y `/productos` con Basic Auth, igual que el resto de la API, o darnos un endpoint equivalente?"*
- **Pistas del portal web de MisRx (capturas de pantalla del usuario, mismo registro de nro. afiliado 2533):** el campo "Monodroga" del portal tiene autocompletado por nombre (escribir "pol" trae una lista de drogas que empiezan así) — confirma visualmente el mismo buscador de arriba. El dropdown "Periodo" del portal mostraba **"plazo mensual"** para este registro, mientras que el `GET` de la API devuelve **"mensual calendario"** — mismo campo, etiquetas distintas entre portal y API (ya resuelto: ver el punto del `0/1/2` más arriba).

#### RESUELTO (2026-08-04): catálogo de `monodroga_id`/`producto_id` — vademécum Alfabeta completo, sin depender de MisRx

El usuario aportó un Google Sheet propio ("un vademécum que le habrán pasado en algún momento") — se descargó y verificó, y **es exactamente el catálogo Alfabeta completo**, con las mismas columnas y códigos que usa `prescripcionABM`:

- **Fuente:** `https://docs.google.com/spreadsheets/d/1lFNnjCyr6mkf46TZl0_eYn3BOlvfLdO8/` (descargable públicamente vía `.../export?format=xlsx`, no requiere login de Google). **21.183 filas.**
- **Columnas:** `intproductos` (= `producto_id`), `nombre` (comercial), `presentacion`, `labonom` (laboratorio), `troquel`, `codigobarra`, `fechavig`, `precio`, `intmonodroga` (= `monodroga_id`), `monodroganom`, `accionfarmanom`, `potencia`, `potencianombre`, `unidadnombre`.
- **Verificado contra los 2 registros reales ya conocidos — coincide exacto:**
  - `intmonodroga 9066` → `valproico,ác.` (marcas: DEPAKENE y otras) ✅ coincide con el registro de nro. afiliado 2533.
  - `intmonodroga 554` → `risperidona` (marcas: DOZIC y otras) ✅ coincide con el registro de nro. afiliado 2227.
  - `intproductos 21153` y `22207` → ambos `RISPERDAL` (risperidona) ✅ coincide con los 2 productos del registro de 2227.
  - `intproductos 761200013` → `valproico,ác.` ✅ coincide con el producto del registro de 2533.
- **Esto cierra el gap por completo:** ya no hace falta el buscador del portal (`/monodrogas`/`/productos`, protegidos por sesión) ni pedirle nada a soporte para poder armar un `POST` de alta con una molécula nueva — alcanza con buscar por nombre en este archivo (columnas `monodroganom`/`nombre`) para obtener el `monodroga_id`/`producto_id` correctos.
- **A tener en cuenta:** tiene columna `fechavig` (fecha de vigencia del precio/registro) — es un dato vivo, conviene volver a descargarlo periódicamente en vez de asumir que queda estático. El archivo no se versionó en el repo (es grande, ~2MB, y son datos de terceros/Alfabeta) — queda documentada la URL de origen acá para volver a bajarlo cuando haga falta.

---

## 5. Patologías

### `GET /patologias/{convenio_id}`
- **Qué hace:** lista las patologías habilitadas/cargadas para el convenio — el catálogo de `patologia_id` que después se usa en `prescripcionABM`.
- **Parámetros:** `convenio_id` (path, requerido).
- **Respuesta:** `patologiasLista` — `patologia_id` + descripción.
- **Utilidad:** catálogo de referencia, necesario únicamente como insumo si se llega a usar el ABM de prescripciones (sección 4).

---

## 6. Autorizaciones

Un circuito paralelo al de "receta": autorizar de antemano una cobertura (por ejemplo, para que la farmacia sepa que ya está aprobada aunque la receta física se presente después), en vez de validar directamente contra la receta.

### `PUT /autorizacion`
- **Qué hace:** autoriza una nueva receta antes de su validación en farmacia.
- **Parámetros:** `clave_id`, body `newAutorizacion`.
- **Body (requeridos):** `convenio_id`, `nro_recetario`, `afiliado_documento`, `afiliado_credencial`, `medico_tipo_mat`, `medico_nro_mat`, `medico_nombres`, `fecha_receta`, `items[]` (cada uno: `nro_item`, `cantidad`, `troquel`, `codbarras`, opcional `porc_cobertura`/`alfabeta`). Opcionales: CUIL/nombre/sexo/categoría/fecha nacimiento del afiliado, `cuf_farmacia`, `observaciones`.
- **Respuesta:** `resp_autorizacion` — `cod_autorizacion` + detalle por ítem autorizado (con posibles errores por ítem).
- **Utilidad:** flujo de "autorización previa" para tratamientos que requieren aprobación antes de dispensarse (ej. medicación de alto costo) — GM Salud podría usarlo si hoy autoriza este tipo de casos manualmente.

### `DELETE /autorizacion`
- **Qué hace:** anula una autorización existente.
- **Parámetros:** `clave_id`, `cod_autorizacion` (requerido).
- **Respuesta:** 204 o error.
- **Utilidad:** revertir una autorización cargada por error o vencida.

### `GET /autorizacion`
- **Qué hace:** consulta el detalle de una autorización por su código.
- **Parámetros:** `clave_id`, `cod_autorizacion` (requerido).
- **Respuesta:** `consulta_autorizacion` — si ya fue validada (`validada`), farmacia, observaciones, ítems.
- **Utilidad:** verificar el estado de una autorización puntual (¿ya la usó el afiliado en una farmacia o sigue pendiente?).

---

## 7. Padrones (ya integrado)

### `GET /padrones/registros/{convenio_id}`
- **Ya en uso** en `misrx_client.obtener_ultimo_registro()`.
- **Qué hace:** historial de cargas de padrón del convenio (qué se subió, cuándo, resultado agregado).
- **Parámetros:** `convenio_id` (path), `start` (paginación, default 0), `limit` (default ALL).
- **Respuesta:** `resp_padrones_registros` — por cada carga: estado de procesamiento, usuario, fecha, info (mensaje de detalle).
- **Nota ya documentada en TASK-002:** este endpoint es el **historial de cargas**, no el padrón vigente — no existe endpoint para leer el listado actual de afiliados cargados en MisRx (confirmado el 2026-08-03).

### `POST /padrones/cargar/{convenio_id}`
- **Ya en uso** en `misrx_client.subir_padron()`.
- **Qué hace:** sube/actualiza el padrón completo del convenio.
- **Parámetros:** `convenio_id` (path), `archivo` (formData, archivo TXT/CSV, requerido).
- **Respuesta:** `resp_padron_carga` — `success` + array de mensajes (`data`).

---

## 8. Consultas (motor de reportes genéricos)

Un mecanismo aparte de "consultas predefinidas" que MisRx habilita por usuario/convenio — son reportes ad-hoc que Preserfar configura del lado de ellos, no endpoints fijos por tema.

### `GET /consultas/disponibles`
- **Qué hace:** lista las consultas que el usuario/convenio tiene habilitadas, con la info de qué parámetros requiere cada una.
- **Parámetros:** `convenio_id` (query, opcional, default 0 = todas).
- **Respuesta real:** *(probado en vivo el 2026-08-04 contra `convenio_id=938` con las credenciales de producción — el spec documentaba mal el schema de respuesta, `resp_padron_carga` era incorrecto)*: `{"data": [{"funciones_consulta_id": ..., "descripcion": ..., "params": [...]}]}`. Para nuestro convenio hay **9 consultas habilitadas**:

  | `funciones_consulta_id` | Descripción | Parámetros |
  |---|---|---|
  | 14 | Afiliado Consumo Detallado | `convenio_id`, `nro_afiliado_dni` (opcional), `nro_afiliado_cred` (opcional) |
  | 205 | Farmacias CUF listado completo | *(sin parámetros)* |
  | 196 | Link impresión (Recetario) | `convenio_id`, `nrorecetario_receta` |
  | 270 | Prestaciones Digitales - órdenes y certificados | `convenio_id`, `periodo` (AAAAMM) |
  | 116 | Recetas Digitales | `convenio_id`, `periodo` (AAAAMM) |
  | 189 | Recetas electrónicas - Consulta por DNI | `convenio_id`, `dni` |
  | 41 | Reporte Recetas Presentadas por Periodo | `convenio_id`, `periodo` (AAAAMM) |
  | 10 | Reporte Recetas Validadas por Periodo | `convenio_id`, `periodo` (AAAAMM) |
  | 11 | Reporte Recetas Validadas por Periodo y Plan | `convenio_id`, `periodo_desde`, `periodo_hasta`, `plan_id` |

- **Utilidad:** punto de entrada para descubrir qué reportes ya tenemos habilitados sin tener que preguntarle a soporte — **ya probado, confirmado funcionando**. Ninguna de las 9 es "padrón vigente cargado" (el hallazgo de TASK-002 sigue en pie: no hay forma de leer el padrón activo vía API), pero **"Afiliado Consumo Detallado" (id 14)** es la más prometedora para un cruce de integridad padrón-vs-consumo (ver prueba real más abajo).

#### Prueba real de `POST /consultas/consultar/14` (Afiliado Consumo Detallado) — 2026-08-04

- Llamado con `{"convenio_id": 938}` **sin** `nro_afiliado_dni`/`nro_afiliado_cred` → `{"total_reg": 0, "data": [], "success": true}`. Conclusión: aunque el spec marca esos dos parámetros como `allowBlank: true` (validación de UI), en la práctica **el backend requiere DNI o credencial** — no devuelve el consumo completo del convenio de una sola vez.
- Probado con 8 DNIs reales activos del padrón (`gx/MisRxAfiliados.csv`): la mitad tenía consumo registrado (2 a 5 recetas cada uno), la otra mitad `total_reg: 0` (afiliados sin recetas validadas en el historial).
- **Campos que devuelve cada registro** (uno por ítem de receta validado): `Cod_Validacion`, `Recetario`, `Recetario Asignado`, `Fecha_Validacion`, `Fecha Prescripción` *(el nombre de esta clave viene con un problema de encoding UTF-8 del lado de MisRx — no es un typo nuestro)*, `Producto`, `Presentacion`, `Unidades`, `CUF`, `Farmacia_Nombre`, `Farmacia_CUIT`, `Nro_Doc`, `Nro_Afiliado`, `Afiliado` (nombre completo), `Medico_Tipo_Matricula`, `Medico_Matricula`, `Medico_Nombre`, `Nro_Item_Receta`, `Laboratorio`, `Monodroga`, `Troquel`, `Codigo_Barra`, `PVP`, `Total_PVP`, `Porc_Cobertura`, `Cobertura` (importe cubierto), `plan` (código numérico), `Estado` (ej. `"Pendiente"` — sugiere que hay más valores posibles, probablemente ligado al circuito de facturación), y `cupon` (link HTML `<a>` ya armado al PDF del comprobante, equivalente a llamar `GET /receta/cupon/{codvalidacion}` a mano).
- **Confirma y refina la utilidad:** es esencialmente lo mismo que `GET /receta/{convenio_id}` filtrado por `dni`, pero con más campos por ítem (incluye laboratorio/monodroga, cupón ya armado como link, y el campo `Estado` de facturación) y sin necesitar rango de fechas obligatorio. Para un cruce masivo padrón-vs-consumo (recorrer todos los DNIs activos) es viable pero requiere una llamada por DNI — con ~1180 afiliados activos son ~1180 requests, hay que evaluar tiempos/rate limits antes de automatizarlo.

#### Pantalla implementada (2026-08-04): `/padron/consumos/` ("Recetas y consumos")

Igual que crónicos, es un consumo real del panel Django (`filter_app/padron/`), no solo investigación. Consulta por DNI (no hace falta resolver `nro_afiliado` contra GX primero, `nro_afiliado_dni` alcanza) contra `POST /consultas/consultar/14`, muestra info del afiliado en GX si existe (convenio ya mapeado a OSFOT/OSPENA, ver arriba) y la tabla de recetas validadas devueltas por MisRx.

- **Normalización de la respuesta** (`padron/services/misrx_client.py::normalizar_item_consumo`): la clave `Fecha Prescripción` se busca por prefijo (`"Fecha"` y distinta de `Fecha_Validacion`) en vez de nombre exacto, porque el carácter con problema de encoding varía según cómo lo decodifique el cliente — confirmado en vivo, la clave real llega como `'Fecha Prescripci�n'` (repr de Python). El campo `cupon` (HTML `<a>` armado por MisRx) se procesa con una regex para extraer solo la URL — se evita renderizar HTML ajeno con `|safe` en el template, por seguridad (no hay control sobre lo que MisRx podría devolver ahí).
- **Migración `0009_consumoconsultalog.py`**: modelo `ConsumoConsultaLog` — a diferencia de `CronicoLog`, no tiene `estado_anterior`/`payload_enviado` porque es una pantalla 100% de lectura, no hay nada que revertir.
- **Permisos — variante del patrón de crónicos, no el mismo:** en crónicos el permiso para operar (`can_manage_cronicos`) está abierto a Operador pero el detalle de bitácora queda solo para admin, porque hay una acción de escritura de por medio (alta/baja real en MisRx) que amerita ese control extra. Acá **no hay ninguna escritura** — solo se lee y se registra quién consultó qué. Por eso hay un único permiso (`can_view_consumos`, migración `0010_operador_permiso_consumos.py`) que habilita tanto hacer la consulta como ver la bitácora completa de consultas anteriores (`ConsumoConsultaLog`), y está abierto a Operador desde el arranque. Ver la aclaración agregada a [[feedback-rollback-features-sensibles]] sobre cuándo aplica el split "puede operar" vs "puede ver todo" (acciones que escriben o son difíciles de deshacer) y cuándo no (consultas puras).
- **Bitácora:** cada búsqueda por DNI (tenga o no resultados, falle o no la llamada a MisRx) queda registrada en `ConsumoConsultaLog` con usuario, DNI consultado, cantidad de recetas encontradas y si hubo error — visible para cualquiera con `can_view_consumos`, no solo admin.

### `POST /consultas/consultar/{consulta_id}`
- **Qué hace:** ejecuta una consulta predefinida por su ID.
- **Parámetros:** `consulta_id` (path, requerido), body: JSON con los parámetros que pida esa consulta particular, o `{}` si no requiere ninguno.
- **Respuesta:** `resp_consulta` — `success`, `total_reg`, `data[]` (array de strings — formato específico depende de la consulta).
- **Utilidad:** ejecutar reportes a medida ya configurados por MisRx para el convenio (ej. podría ser exactamente el reporte "padrón vigente" que hoy no existe como endpoint fijo — vale la pena llamar primero a `/consultas/disponibles` para ver si algo así ya está habilitado antes de asumir que no existe ningún camino).

---

## 8bis. Investigación (2026-08-04): ¿se puede saber si un afiliado está Activo/Inactivo en MisRx vía API?

**Motivación:** el portal web de MisRx tiene una pantalla desde la que se puede exportar manualmente un CSV (`gx/Afiliados.csv`, `gx/MisRxAfiliados.csv` en este repo) con columnas `Nro.Afiliado, DNI, Apellido, Nombres, Sexo, Fecha_Nacimiento, Clase, Estado (Activo/Inactivo), credencial, centrocosto` — es decir, **el padrón vigente real con estado por afiliado**, exactamente el dato que TASK-002 concluyó que no se podía leer por API. La idea a investigar: ¿alguno de los endpoints/consultas ya disponibles trae ese mismo dato, aunque sea disfrazado de otra cosa (ej. usar consumo de recetas como proxy de "está activo")?

**Se probó en vivo, con DNIs y números de afiliado reales tomados de ese mismo CSV:**

1. **Usar consumo como proxy de actividad (la idea original a validar):** no funciona de forma confiable. `POST /consultas/consultar/14` y `POST /consultas/consultar/189` devuelven `total_reg: 0` tanto para afiliados que nunca consumieron (pero están **Activos**) como — presumiblemente — para inactivos. La ausencia de recetas no distingue "activo sin consumo" de "inactivo": **no es un proxy válido de estado**.
2. **`GET /prescripcion/{convenio_id}?nroafiliado=...`** — el schema `prescripcionConsulta` del spec sí declara un campo `afiliados_estado` (justo lo que buscábamos), pero probado con números de afiliado reales (uno Activo, uno Inactivo) ambos devolvieron `{"total": 0, "data": []}`: ese campo solo se completa si el afiliado tiene una prescripción crónica cargada, algo raro — tampoco sirve como chequeo general.
3. **Los campos `estado`/`Estado` que sí devuelven las consultas de recetas** (ej. `"Dispensada"` en consulta 189, `"Pendiente"` en consulta 14) son el estado **de la receta/validación**, no del afiliado — coincidencia de nombre, no de significado.
4. **Se probaron rutas siguiendo el mismo patrón de nombres que la API documentada** (`/padrones/afiliados/{id}`, `/padrones/listado/{id}`, `/padrones/estado/{id}`, `/padrones/{id}`, `/afiliados/{id}`, `/afiliado/{id}`), por si existiera un endpoint real no listado en el spec público. Resultado revelador:
   - `/padrones/afiliados`, `/padrones/listado`, `/padrones/estado`, `/padrones/{id}` → 404 genérico (no existen, ni con otra auth).
   - **`/afiliados/{convenio_id}` y `/afiliado/{convenio_id}` → 404 pero con el mensaje `"No hay nada en esta URL o la session no es valida"`** — a diferencia del resto, esto indica que esas rutas **sí existen** en el backend de MisRx, pero están protegidas por **sesión web (cookie de login del portal)**, no por el Basic Auth de la API REST pública. Es casi seguro que la pantalla de exportación manual del portal usa exactamente esta ruta internamente.

**Conclusión:** con la API REST pública y las credenciales Basic Auth actuales, **no hay forma de leer el estado Activo/Inactivo real de un afiliado**, ni directamente ni por proxy de consumo. El dato existe y se sirve del lado de MisRx (por eso el export manual funciona), pero por una vía de autenticación distinta (sesión de portal) que la API pública no expone.

**Siguiente paso recomendado (no bloqueante, no es código):** escribirle a soporte Preserfar (soporte@preserfar.com) preguntando puntualmente **si existe o se puede habilitar una "consulta" (dentro del motor `/consultas/consultar/{id}`) que devuelva el padrón/estado de afiliados por convenio** — dado que las 9 consultas habilitadas hoy ya cubren varios reportes de recetas, es razonable pedir que agreguen una equivalente al export manual de "Afiliados con Estado". Si acceden, sería la solución definitiva al hallazgo pendiente de TASK-002 (verificar que lo que MisRx tiene cargado coincide con lo que le mandamos) sin depender de scraping de sesión web, que sería frágil y no es un camino recomendable.

---

## 8ter. Manual general del portal para Obras Sociales (Preserfar, 2013) — qué tiene el portal que la API no expone

El usuario aportó un segundo PDF (`gx/MisValidaciones Instructivos Obra Social (1) (1).pdf`) — el manual completo del portal web para el rol "Obra Social" (no específico de crónicos como el otro). Aunque es de 2013, la estructura de módulos sigue siendo la misma que se ve en las capturas de pantalla actuales. Sirve para mapear **qué de todo lo que puede hacer un administrador de convenio en el portal tiene o no un endpoint equivalente en la API pública**:

| Módulo del portal | Qué hace | ¿Tiene equivalente en la API? |
|---|---|---|
| Gestión de Afiliados | Alta/edición de afiliados, ver Consumos por mes, asignar Planes Especiales, cargar Prescripciones (si el plan es Crónico) | Parcial: `GET/POST /prescripcion/{convenio_id}` cubre prescripciones. **No hay API para alta/edición de datos del afiliado en sí** (eso lo sigue haciendo el padrón vía `POST /padrones/cargar`) |
| Gestión de Planes | Configurar planes, VDM por plan, farmacias habilitadas, reglas (sexo/edad/topes) | **No, portal-only.** Es configuración estructural que hace MisRx/el administrador del convenio, no algo pensado para automatizar |
| Reposiciones | Seguimiento de pedidos a la droguería para medicamentos con reposición automática | **No, sin endpoint conocido** |
| Gestión de Presentaciones de Farmacia | Lotes de recetas, recepción, cierres para facturación | Parcial: `POST /receta/registra_factura` cubre la asociación de una factura a una validación puntual, pero no el flujo completo de lotes/cierres |
| Farmacias Datos | Listado de farmacias adheridas al convenio | Sí — coincide con la consulta `205` ("Farmacias CUF listado completo") que ya tenemos habilitada |
| Estadísticas (Control de Gastos, Ranking Productos, Ranking Afiliados) | Gráficos y reportes agregados por período | Parcial — las consultas `10`/`11`/`41` (recetas validadas/presentadas por período) se acercan, pero no hay un equivalente exacto a "Ranking por Afiliado" |
| Consultas | Motor de reportes configurables por convenio — el manual da como **ejemplos**: *"Reporte Recetas Validadas por Periodo y Plan"*, *"Listado de Farmacias habilitadas en Plan Insulinas"*, **`"Listado Actual de Afiliados con Cronicidades"`**, *"Gasto Anual de Afiliados Crónicos detallado por Producto"*, *"Gasto Anual de Afiliados Crónico Totalizado"* | Es el mismo motor de `/consultas/disponibles` + `/consultas/consultar/{id}` (sección 8) — **`"Listado Actual de Afiliados con Cronicidades"` es EXACTAMENTE el reporte que resolvería el barrido manual de 3335 afiliados que se tuvo que hacer hoy**, y no está entre las 9 consultas habilitadas para nuestro convenio. **Pedido concreto recomendado a soporte:** pedir que habiliten esa consulta puntual (por nombre, tal como aparece en su propio manual) para el convenio 938 |
| Autorizar Recetas / Recetas Autorizadas | Autorizar una receta de antemano (excede topes, o crónicos individuales) | Sí — `PUT`/`GET`/`DELETE /autorizacion` (sección 6) |
| Validación de una Receta | Simular/validar una receta de un afiliado | Sí — `POST /receta` (sección 2). **El manual documenta explícitamente que si el afiliado está "inactivo o bloqueado", el botón de selección se desactiva** — confirma institucionalmente el mismo criterio de guardrail que ya se implementó en `/padron/cronicos/` (bloquear acciones sobre afiliados no activos) |
| Planes VDM Consulta | Vademécum por plan (Troquel, Código de Barras, Monodroga, Laboratorio, Presentación, Potencia) | No hay endpoint documentado — pero el vademécum Alfabeta encontrado (ver sección 4) cubre la misma necesidad de forma independiente |
| Consulta de Prescripciones | **Listado completo** de todos los afiliados con prescripciones crónicas y sus productos, exportable a Excel | Esto es justamente lo que el barrido manual de 3335 afiliados tuvo que reconstruir a fuerza de bruta porque `GET /prescripcion/{convenio_id}` solo permite consultar de a un afiliado/prescripción por vez, no un listado completo — otra confirmación de que **"Listado Actual de Afiliados con Cronicidades" (o esta pantalla) es el pedido correcto para hacerle a soporte** |
| Consulta Web | Formulario de soporte integrado al portal (consultas/sugerencias/inconvenientes) | No es un endpoint de datos — es un canal de contacto alternativo al mail de soporte@preserfar.com |

---

## 9. Resumen ejecutivo — qué usamos, qué serviría para expandir

**Hoy en uso:** solo padrones (carga + historial). El resto de la API está sin explorar en la práctica.

**Ideas de expansión, de mayor a menor relevancia estimada para GM Salud:**

1. ~~`GET /consultas/disponibles`~~, ~~`POST /consultas/consultar/14`~~, ~~`POST /consultas/consultar/189`~~, ~~`GET /prescripcion/{convenio_id}`~~ y sondeo de rutas no documentadas — **todo ya probado en vivo (2026-08-04)** contra producción con DNIs/números de afiliado reales. Confirmado y cerrado: **no existe ningún camino, ni directo ni por proxy de consumo, para leer el estado Activo/Inactivo real de un afiliado vía la API REST pública** — ver investigación completa en la sección 8bis, incluido el hallazgo de que `/afiliados/{convenio_id}` existe en el backend de MisRx pero requiere sesión de portal, no Basic Auth. Único camino que queda: pedirle a soporte Preserfar que habilite una consulta nueva para esto.
2. **`GET /receta/{convenio_id}`** — traer el consumo de recetas validadas por período/DNI. Permitiría un dashboard de consumo en el panel `/padron/` y detectar afiliados que consumen sin estar activos en el padrón que enviamos (cruce de integridad, relacionado al mismo hallazgo pendiente de TASK-002).
3. **Prescripciones (`GET`/`POST /prescripcion/{convenio_id}`)** — **ya implementado y probado en vivo (pantalla `/padron/cronicos/`, ver sección 4)**: consulta por DNI funcionando, y el `POST` de alta/baja documentado y listo para probarse (falta solo que el usuario dispare el primer `POST` real desde el navegador — el entorno de este asistente no puede hacer llamadas de escritura a producción). El catálogo `monodroga_id`/`producto_id` que parecía un bloqueante **ya está resuelto** con el vademécum Alfabeta que aportó el usuario (sección 4) — no hace falta esperar a soporte MisRx para esto.
4. **Autorizaciones (`PUT`/`GET`/`DELETE /autorizacion`)** — similar a prescripciones pero para autorizaciones puntuales (no recurrentes), útil si hay un flujo manual de "autorizar antes de que el afiliado vaya a la farmacia".
5. **`GET /receta/digitales/{convenio_id}`** y **`GET /receta/prescripcion/{nrorecetario}/{convenio_id}`** — buscadores de recetas digitales por afiliado, útiles para un módulo de atención (responder "¿qué le cubrieron a este DNI?"). Requieren `clave_id`, que no está configurado — hay que pedirlo a soporte.
6. **`GET /receta/cupon/{codvalidacion}`** — reimpresión de comprobantes, caso de uso menor (atención puntual a un reclamo).
7. Endpoints de **escritura de recetas/facturación** (`POST/DELETE /receta`, `POST /receta/registra_factura`, `POST /receta/adesfa`) — son para software de farmacia, no aplican a GM Salud como obra social/cliente consumidor de estos servicios.

**Dato pendiente para cualquiera de las opciones 2–6:** confirmar con soporte MisRx (soporte@preserfar.com) si nuestras credenciales actuales ya tienen `clave_id` asignado o si hay que solicitarlo — varios endpoints de "Recetas" lo piden como parámetro obligatorio además del Basic Auth, y no está en nuestro `.env` hoy.
