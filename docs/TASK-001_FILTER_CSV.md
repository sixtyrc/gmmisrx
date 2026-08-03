# TASK-001_FILTER_CSV: Filtro de CSV a partir de Excel

## Objetivo
Crear un pequeño sistema web (interfaz sencilla) que reciba:
1. `archivo1` (Excel): Contiene un listado de personas a excluir (columna `DNI`).
2. `archivo2` (CSV): Padrón maestro (columna `Nro Documento`, separador `;`).

Debe generar:
- `archivo3` (CSV): Un archivo de salida idéntico en formato a `archivo2.csv`, pero sin las filas cuyo `Nro Documento` coincida con un `DNI` de `archivo1.xlsx`.

## Decisiones Técnicas
- **Stack:** Django (LTS) nativo para rapidez dado lo puntual del requerimiento (HTML/CSS directo), salvo que se exija el stack de React.
- **Librerías:** `pandas` y `openpyxl` para el procesamiento rápido en memoria de los archivos.
- **Lógica de Cruce:** Se extraerán los `DNI` del Excel a un *set*, y luego se iterará o filtrará el dataframe del CSV, quitando coincidencias.

## Decisiones del Usuario / Resultados
- **Stack:** Django clásico sin React y sin base de datos (PostgreSQL), priorizando simplicidad.
- **Ubicación:** Inicializado en `D:\Proyectos\Gm-MisRx\filter_app`.
- **Limpieza de Datos:** Sin alterar formatos (conservando espacios originales en el archivo de salida para compatibilidad con la plataforma de destino).
- **Nombre de salida:** Siempre `AfiliadosGM_Ospena_YYYYMMDD_HHMMSS.csv`.
- **Estadísticas:** El sistema calcula y muestra totales en pantalla (Excel total, CSV total, eliminados, restantes) y provee descarga diferida del archivo procesado.

## Bitácora de Ajustes (Problemas y Soluciones)
### 2026-08-01 - Error de cabeceras en Excel
- **Problema:** El Excel tenía el encabezado `DNI` en la fila 5, resultando en error de columna no encontrada al procesar.
- **Causa:** Por defecto, `pd.read_excel` busca las columnas en la primera fila.
- **Solución:** Se implementó una lógica de escaneo que busca el string `"DNI"` en las primeras 20 filas del Excel y re-lee el archivo asignando dinámicamente el `header_row` correspondiente.

### 2026-08-01 - Discrepancia de tipos numéricos
- **Problema:** Los DNIs leídos del Excel se interpretaban como flotantes (ej: `14554079.0`) mientras que en el CSV eran strings (ej: `14554079`), impidiendo el cruce exacto.
- **Causa:** Comportamiento estándar de pandas al encontrar valores nulos o celdas con formato de celda flotante en Excel.
- **Solución:** Se implementó la limpieza `clean_excel_dni` para sustraer la extensión `.0` de los strings convertidos antes del cruce.

### 2026-08-01 - Reporte de No Encontrados
- **Problema/Requerimiento:** El usuario requería descargar los afiliados del Excel que no pudieron ser cruzados en el CSV para saber cuáles no se procesaron.
- **Solución:** Se agregó un procesamiento paralelo que busca diferencias (DNI Excel que no está en CSV), extrae dinámicamente las columnas relevantes (`DNI`, `CUIL`, `Nombre`, `Apellido` de forma insensible a mayúsculas) y provee un enlace de descarga específico en el cartel de advertencia de estadísticas.

### 2026-08-01 - Caso de soporte: Doble filtrado accidental
- **Incidencia:** Al re-procesar, el usuario observó que solo quedaban 1168 registros y que el reporte de "No Encontrados" creció a ~101KB.
- **Causa:** El usuario subió como entrada el CSV que ya había sido filtrado en la primera ejecución (`1180` registros) en lugar de subir el padrón original de `2300` registros. Al hacer esto, el Excel de bajas no encontró casi ningún DNI coincidente (ya habían sido borrados), resultando en un archivo de "No Encontrados" masivo y solo 12 exclusiones nuevas.
- **Solución:** Se aclaró el flujo operativo (siempre usar el padrón maestro original como CSV de entrada). No requiere cambios de código.
