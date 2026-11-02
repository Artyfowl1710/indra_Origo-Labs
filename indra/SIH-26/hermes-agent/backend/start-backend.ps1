$ErrorActionPreference = 'Stop'
$backendRoot = $PSScriptRoot
$repoRoot = Split-Path -Parent $backendRoot
$llamaSwap = @("$backendRoot\bin\llama-swap.exe", "$backendRoot\bin\llama-swap") |
    Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$backendPython = @(
    "$backendRoot\venv\Scripts\python.exe",
    "$repoRoot\venv\Scripts\python.exe"
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $llamaSwap) { throw "llama-swap is missing. Run install-indra.ps1 first." }
if (-not $backendPython) { throw "Managed Python environment is missing. Repair the INDRA installation." }
if (-not (Test-Path -LiteralPath "$backendRoot\bin\llama-server.exe") -and
    -not (Test-Path -LiteralPath "$backendRoot\bin\llama-server")) {
    throw "llama-server is missing. Run install-indra.ps1 first."
}
New-Item -ItemType Directory -Force -Path "$backendRoot\data" | Out-Null

# This file is generated on the destination machine. Never trust a checked-in
# developer path because llama-swap executes it verbatim.
& $backendPython "$backendRoot\auto-configure-models.py"
if ($LASTEXITCODE -ne 0) { throw "Could not generate the portable llama-swap configuration." }

# Generate a per-install credential when the installer has not provisioned one.
$envFile = "$backendRoot\.env"
if (-not (Test-Path -LiteralPath $envFile) -or
    -not (Select-String -LiteralPath $envFile -Pattern '^WORKBENCH_API_KEY=.{16,}$' -Quiet)) {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    # BitConverter works in both Windows PowerShell 5.1 and PowerShell 7.
    $key = 'wb_local_' + (([BitConverter]::ToString($bytes) -replace '-', '').ToLowerInvariant())
    @(
        "WORKBENCH_API_KEY=$key"
        'TERMINAL_ENV=local'
        'ALLOW_HF_DOWNLOAD=false'
        'ALLOW_RAW_WORKFLOW=false'
    ) | Set-Content -LiteralPath $envFile -Encoding utf8
}
function Test-BackendPort([int]$port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try { $client.Connect('127.0.0.1', $port); return $true }
    catch { return $false }
    finally { $client.Dispose() }
}
function Start-BackendPart($name, $port, $executable, $arguments) {
    if (Test-BackendPort $port) { return }
    # Start-Process fails when a parent process carries both PATH and Path.
    # Build a case-insensitive, de-duplicated environment for Windows instead.
    $info = [System.Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $executable
    $info.Arguments = $arguments
    $info.WorkingDirectory = $backendRoot
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($entry in [System.Environment]::GetEnvironmentVariables().GetEnumerator()) {
        if ($seen.Add([string]$entry.Key)) { $info.Environment[[string]$entry.Key] = [string]$entry.Value }
    }
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $info
    [void]$process.Start()
    $deadline = (Get-Date).AddSeconds(45)
    while (-not (Test-BackendPort $port)) {
        if ($process.HasExited) { throw "$name exited during startup with code $($process.ExitCode)." }
        if ((Get-Date) -gt $deadline) { throw "$name did not start on port $port within 45 seconds." }
        Start-Sleep -Milliseconds 400
    }
}
# Qdrant is intentionally omitted for the offline skills-based demo.
Start-BackendPart 'llamaswap' 8100 $llamaSwap '--config config/llama-swap.yaml --listen 127.0.0.1:8100 --watch-config'
Start-BackendPart 'workbench' 8000 $backendPython '-m uvicorn server.app:app --host 127.0.0.1 --port 8000'
