$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$backendPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $backendPython)) {
    throw 'Jalankan py setup.py terlebih dahulu.'
}
& $backendPython -m uvicorn app.main:app --reload
exit $LASTEXITCODE
