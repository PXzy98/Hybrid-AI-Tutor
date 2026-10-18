param([string]$PythonPath = "")
$ErrorActionPreference = "Stop"
$projectDir = $PSScriptRoot
if (-not $PythonPath) {
    $PythonPath = Join-Path $projectDir ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Run setup_local.py first, or pass -PythonPath with an existing virtualenv Python."
}
$PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
$env:APP_CONFIG = Join-Path $projectDir "config.yaml"
Set-Location (Join-Path $projectDir "backend")
& $PythonPath -m uvicorn app.main:app --reload
if ($LASTEXITCODE -ne 0) { throw "Backend stopped with an error; see the output above." }
