$ErrorActionPreference = "Stop"
$projectDir = $PSScriptRoot
Set-Location (Join-Path $projectDir "frontend")
if (-not (Test-Path "node_modules")) {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
}
npm run dev -- --host 127.0.0.1
if ($LASTEXITCODE -ne 0) { throw "Frontend stopped with an error; see the output above." }
