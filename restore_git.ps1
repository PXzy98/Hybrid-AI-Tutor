$ErrorActionPreference = "Stop"
$projectDir = $PSScriptRoot
$gitDir = Join-Path $projectDir ".git"
$bundle = Join-Path $projectDir "handoff\integration.bundle"
$branch = "integration/main-rag-semantic"
if (Test-Path -LiteralPath $gitDir) {
    throw "This folder already has Git metadata. Existing Git history has not been changed."
}
if (-not (Test-Path -LiteralPath $bundle)) {
    throw "Git bundle not found. Use the complete project ZIP, including handoff/integration.bundle."
}
Set-Location $projectDir
git clone --bare --branch $branch "$bundle" "$gitDir"
if ($LASTEXITCODE -ne 0) { throw "Could not restore the Git branch." }
git --git-dir="$gitDir" config core.bare false
if ($LASTEXITCODE -ne 0) { throw "Could not configure the working repository." }
git reset --mixed HEAD
if ($LASTEXITCODE -ne 0) { throw "Could not populate the Git index; project files were not overwritten." }
$remotes = @(git remote)
if ($remotes -contains "origin") {
    git remote remove origin
    if ($LASTEXITCODE -ne 0) { throw "Could not replace the bundle remote." }
}
git remote add origin https://github.com/PXzy98/Hybrid-AI-Tutor.git
if ($LASTEXITCODE -ne 0) { throw "Could not set the GitHub remote." }
git branch --show-current
Write-Host "Local integration branch restored. Project files, .env and data were kept."
Write-Host "After testing, upload with: git push -u origin integration/main-rag-semantic"
