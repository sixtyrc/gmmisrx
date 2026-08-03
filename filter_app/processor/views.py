import io
import os
import uuid

import pandas as pd
from datetime import datetime
from django.shortcuts import render
from django.http import HttpResponse, Http404
from django.conf import settings


TEMP_DIR = os.path.join(settings.BASE_DIR, 'tmp_downloads')
os.makedirs(TEMP_DIR, exist_ok=True)


def filter_files(request):
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        csv_file = request.FILES.get('csv_file')

        if not excel_file or not csv_file:
            return render(request, 'processor/upload.html', {'error': 'Por favor, subí ambos archivos.'})

        try:
            excel_bytes = excel_file.read()

            # 1. Leer el Excel (columna DNI).
            df_excel = pd.read_excel(io.BytesIO(excel_bytes))
            if 'DNI' not in df_excel.columns:
                header_row_idx = None
                df_excel_no_head = pd.read_excel(io.BytesIO(excel_bytes), header=None)
                for i in range(min(20, len(df_excel_no_head))):
                    row_values = df_excel_no_head.iloc[i].astype(str).str.strip().tolist()
                    if 'DNI' in row_values:
                        header_row_idx = i
                        break

                if header_row_idx is not None:
                    df_excel = pd.read_excel(io.BytesIO(excel_bytes), header=header_row_idx)
                else:
                    return render(request, 'processor/upload.html', {'error': 'El archivo Excel no tiene la columna "DNI" en las primeras 20 filas.'})

            # Limpiar DNI del Excel (elimina el ".0" si se parseó como float)
            def clean_dni(val):
                s = str(val).strip()
                if s.endswith('.0'):
                    return s[:-2]
                return s

            dnis_to_remove = set(df_excel['DNI'].dropna().apply(clean_dni))

            # 2. Leer el CSV (columna Nro Documento).
            csv_bytes = csv_file.read()
            try:
                df_csv = pd.read_csv(io.BytesIO(csv_bytes), sep=';', dtype=str, encoding='utf-8')
            except UnicodeDecodeError:
                df_csv = pd.read_csv(io.BytesIO(csv_bytes), sep=';', dtype=str, encoding='latin-1')

            if 'Nro Documento' not in df_csv.columns:
                return render(request, 'processor/upload.html', {'error': 'El archivo CSV no tiene la columna "Nro Documento".'})

            csv_dnis = df_csv['Nro Documento'].fillna('').astype(str).str.strip()
            csv_dnis_set = set(csv_dnis)

            # 3. Filtrar
            mask_removed = csv_dnis.isin(dnis_to_remove)
            df_filtered = df_csv[~mask_removed]

            # 3b. Identificar los DNI del Excel que NO se encontraron en el CSV
            df_excel['_clean_dni'] = df_excel['DNI'].astype(str).apply(clean_dni)
            df_not_found = df_excel[df_excel['_clean_dni'].isin(dnis_to_remove) & ~df_excel['_clean_dni'].isin(csv_dnis_set)]
            
            # Buscar columnas relevantes de forma dinámica (ignora mayúsculas/minúsculas)
            cols_to_keep = []
            for col in df_excel.columns:
                col_lower = str(col).lower()
                if any(x in col_lower for x in ['dni', 'documento', 'cuil', 'nombre', 'apellido']):
                    if col != '_clean_dni':
                        cols_to_keep.append(col)
            
            if not cols_to_keep:
                cols_to_keep = ['DNI']
                
            df_not_found_subset = df_not_found[cols_to_keep]

            # 4. Guardar archivo temporal del filtrado principal
            now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"AfiliadosGM_Ospena_{now_str}.csv"
            file_id = str(uuid.uuid4())
            temp_path = os.path.join(TEMP_DIR, f"{file_id}.csv")
            df_filtered.to_csv(temp_path, sep=';', index=False, encoding='utf-8-sig')

            # 4b. Guardar archivo temporal de los no encontrados
            file_id_not_found = ""
            if len(df_not_found) > 0:
                file_id_not_found = str(uuid.uuid4())
                temp_path_not_found = os.path.join(TEMP_DIR, f"{file_id_not_found}.csv")
                df_not_found_subset.to_csv(temp_path_not_found, sep=';', index=False, encoding='utf-8-sig')

            # 5. Calcular estadísticas
            total_excel = len(dnis_to_remove)
            total_csv_original = len(df_csv)
            total_removed = int(mask_removed.sum())
            total_remaining = len(df_filtered)
            dnis_not_found = len(df_not_found)

            stats = {
                'processed': True,
                'total_excel': total_excel,
                'total_csv_original': total_csv_original,
                'total_removed': total_removed,
                'total_remaining': total_remaining,
                'dnis_not_found': dnis_not_found,
                'output_filename': output_filename,
                'file_id': file_id,
                'file_id_not_found': file_id_not_found,
                'not_found_filename': f"NoEncontrados_{now_str}.csv",
            }
            return render(request, 'processor/upload.html', stats)

        except Exception as e:
            return render(request, 'processor/upload.html', {'error': f'Ocurrió un error al procesar: {str(e)}'})

    return render(request, 'processor/upload.html')


def download_file(request, file_id):
    temp_path = os.path.join(TEMP_DIR, f"{file_id}.csv")
    if not os.path.exists(temp_path):
        raise Http404("El archivo ya no está disponible.")

    filename = request.GET.get('name', 'AfiliadosGM_Ospena.csv')

    with open(temp_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # Eliminar archivo temporal después de servir
    os.remove(temp_path)
    return response
