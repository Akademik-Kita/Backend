$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$backendPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $backendPython)) {
    throw 'Jalankan py setup.py terlebih dahulu.'
}
$demoEnvPath = Join-Path $PSScriptRoot '.env.demo'
if (-not (Test-Path -LiteralPath $demoEnvPath)) {
    $demoSecret = & $backendPython -c 'import secrets; print(secrets.token_urlsafe(48))'
    if ($LASTEXITCODE -ne 0) { throw 'Pembuatan konfigurasi demo gagal.' }
    $demoDbPath = (Join-Path $PSScriptRoot 'akademikkita-demo.db').Replace('\', '/')
    $demoConfig = "DATABASE_URL=sqlite:///$demoDbPath`nJWT_SECRET_KEY=$demoSecret`nJWT_ALGORITHM=HS256`nDEMO_MODE=true`nRECOMMENDATION_HARD_FILTERS=false`nCORS_ORIGINS=http://localhost:5173`n"
    [System.IO.File]::WriteAllText($demoEnvPath, $demoConfig)
}
$env:AKADEMIKKITA_ENV_FILE = $demoEnvPath
& $backendPython -m app.cli demo-init
if ($LASTEXITCODE -ne 0) { throw 'Setup demo gagal.' }
& $backendPython -m uvicorn app.main:app --reload --port 8001
exit $LASTEXITCODE
