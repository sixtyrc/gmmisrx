@echo off
echo ==============================================
echo Iniciando Filtro de Afiliados (MisRx)
echo ==============================================

cd filter_app
if not exist "venv\Scripts\activate.bat" (
    echo Error: No se encontro el entorno virtual.
    pause
    exit /b
)

echo Activando entorno virtual...
call venv\Scripts\activate.bat

echo Abriendo navegador en http://localhost:8000/padron/ ...
start http://localhost:8000/padron/

echo Iniciando servidor...
python manage.py runserver 8000

pause
