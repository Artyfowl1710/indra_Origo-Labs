param([string]$ModelDirectory=$env:ORIGO_MODEL_DIR, [ValidateSet('auto','gpu','cpu')][string]$Device='auto')
if (-not $ModelDirectory) { $ModelDirectory=Join-Path $PSScriptRoot 'data\models' }
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1') -ErrorAction Stop
$runtime=Join-Path $env:LOCALAPPDATA 'Programs\Ollama\lib\ollama'
$server=Join-Path $runtime 'llama-server.exe'
$localIssue=''
if (-not (Test-Path -LiteralPath $server -PathType Leaf)) {
 $localIssue='runtime-missing'
} elseif ((Get-AuthenticodeSignature -LiteralPath $server).Status -ne 'Valid') {
 $localIssue='runtime-unverified'
}
foreach ($file in @('Qwen3.5-4B-Q4_K_M.gguf','Qwen2-VL-OCR-2B-Instruct.Q4_K_M.gguf','mmproj-Qwen2-VL-2B-Instruct-f16.gguf')) {
 if (-not $localIssue -and -not (Test-Path -LiteralPath (Join-Path $ModelDirectory $file) -PathType Leaf)) { $localIssue='models-missing' }
}
# Stop only the earlier direct launcher process when its ownership still matches.
$stateFile=Join-Path $PSScriptRoot 'data\cpp-runtime.json'
if (-not $localIssue -and (Test-Path -LiteralPath $stateFile)) {
 $saved=Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
 if ($saved.owner -eq 'origo-cpp' -and ($saved.pid -is [long] -or $saved.pid -is [int])) {
  $owned=Get-CimInstance Win32_Process -Filter "ProcessId=$($saved.pid)" -ErrorAction SilentlyContinue
  if ($owned -and $owned.ExecutablePath -eq $server -and $owned.CommandLine.Contains('--alias '+$saved.alias)) {
   Stop-Process -Id $saved.pid
   Wait-Process -Id $saved.pid -Timeout 10 -ErrorAction SilentlyContinue
  }
 }
}
$env:ORIGO_AUTO_ROUTING=if($localIssue){'0'}else{'1'}
$env:ORIGO_LOCAL_STARTUP_ISSUE=$localIssue
$env:ORIGO_RUNTIME_DIR=$runtime
$env:ORIGO_MODEL_DIR=$ModelDirectory
$env:ORIGO_DEVICE=$Device
$env:ORIGO_HOME=Join-Path $PSScriptRoot 'data\indra-auto-home'
$env:ORIGO_DESKTOP_USER_DATA=Join-Path $PSScriptRoot 'data\origo-auto-desktop'
& (Join-Path $PSScriptRoot 'start_origo_product.ps1')
