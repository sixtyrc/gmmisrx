$ErrorActionPreference = "Stop"

$ProjectDir = "$PSScriptRoot\..\filter_app"
$VenvPath = "$ProjectDir\venv\Scripts\Activate.ps1"

Write-Host "Activando entorno virtual..." -ForegroundColor Cyan
if (Test-Path $VenvPath) {
    . $VenvPath
} else {
    Write-Host "No se encontró el entorno virtual en $VenvPath. Por favor, asegúrate de que exista." -ForegroundColor Red
    exit 1
}

Write-Host "Iniciando servidor de desarrollo Django..." -ForegroundColor Cyan
Set-Location $ProjectDir
python manage.py runserver 8000
