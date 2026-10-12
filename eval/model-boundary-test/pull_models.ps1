# Run on the Ollama server (192.168.2.25) in PowerShell. Use: .\pull_models.ps1 all  to include optional models.
$required = "qwen3.5:2b","qwen3.5:4b","qwen3.5:9b","qwen3.5:27b","gemma4:e4b","gemma4:12b","gemma4:26b"
$optional = "qwen3.5:0.8b","gemma4:e2b","gemma4:31b","qwen3.8:27b","qwen3.5:35b"
$models = $required; if ($args[0] -eq "all") { $models += $optional }
foreach ($m in $models) { Write-Host "== $m"; ollama pull $m; if ($LASTEXITCODE -ne 0) { Write-Host "!! failed: $m (check the tag on ollama.com/library)" } }
ollama list
