@echo off
echo ==============================================
echo Actualizacion diaria del padron MisRx
echo ==============================================

set "PROJECT_ROOT=%~dp0.."
set "APP_DIR=%PROJECT_ROOT%\filter_app"
set "LOG_DIR=%PROJECT_ROOT%\logs"
set "LOG_FILE=%LOG_DIR%\actualizar_padron.log"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

if not exist "%APP_DIR%\venv\Scripts\activate.bat" (
    echo Error: No se encontro el entorno virtual en %APP_DIR%\venv >> "%LOG_FILE%"
    exit /b 1
)

cd /d "%APP_DIR%"

echo ---------------------------------------- >> "%LOG_FILE%"
echo %date% %time% - Iniciando actualizacion de padron (automatico) >> "%LOG_FILE%"

call venv\Scripts\activate.bat
python manage.py actualizar_padron --trigger automatico >> "%LOG_FILE%" 2>&1
set "RESULTADO=%ERRORLEVEL%"

echo %date% %time% - Finalizado (exit code %RESULTADO%) >> "%LOG_FILE%"

exit /b %RESULTADO%
