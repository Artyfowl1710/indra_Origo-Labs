param([string]$ModelDirectory = 'C:\Users\khatr\OneDrive\Desktop\SIH-26-main\SIH-26\hermes-agent\backend\models')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$ollama = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
$definitions = @(@{Name='origo-qwen35';File='Qwen3.5-4B-Q4_K_M.gguf'}, @{Name='origo-gemma2';File='gemma-2-2b-it-Q4_K_M.gguf'})
$directory = Join-Path $root 'data\local-models'
New-Item -ItemType Directory -Force $directory | Out-Null
foreach ($definition in $definitions) {
    $modelPath = Join-Path $ModelDirectory $definition.File
    if (-not (Test-Path -LiteralPath $modelPath)) { throw "Model missing: $modelPath" }
    $file = Join-Path $directory ($definition.Name + '.Modelfile')
    @(('FROM "' + $modelPath + '"'), 'PARAMETER num_ctx 4096', 'PARAMETER temperature 0.2') | Set-Content -LiteralPath $file -Encoding utf8
    & $ollama create $definition.Name -f $file
    if ($LASTEXITCODE -ne 0) { throw "Model import failed: $($definition.Name)" }
}
