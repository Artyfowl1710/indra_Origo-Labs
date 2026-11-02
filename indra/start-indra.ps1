<#
.SYNOPSIS
One-click starter for the complete INDRA system in its best-performing state.

.DESCRIPTION
This script will:
1. Clean up any stale processes on ports 8000, 8100, 9119.
2. Auto-configure model settings (GPU-accelerated Qwen2-VL OCR, ChatML template, Gemma, Qwen 3.5).
3. Start backend services (llama-swap on 8100, workbench gateway on 8000).
4. Register active models.
5. Launch the INDRA Dashboard on 9119 and open the web interface in the default browser.
#>

$ErrorActionPreference = 'Stop'
$rootDir = $PSScriptRoot
$backendDir = "$rootDir\SIH-26\hermes-agent\backend"
$indraExe = "$rootDir\venv\Scripts\indra.exe"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "       STARTING INDRA SYSTEM (ONE-CLICK)  " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 0. Clean stale ports
Write-Host "`n[1/4] Checking ports and cleaning stale instances..." -ForegroundColor Yellow
$ports = 8000, 8100, 9119
foreach ($port in $ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($conn in $connections) {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}
Get-Process | Where-Object { $_.ProcessName -match "llama-server|llama-swap" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 600

# 1. Run Auto-Configure
Write-Host "`n[2/4] Auto-configuring model engines..." -ForegroundColor Yellow
$backendPython = "$backendDir\venv\Scripts\python.exe"
if (-not (Test-Path $backendPython)) {
    $backendPython = "$rootDir\venv\Scripts\python.exe"
}
if (Test-Path $backendPython) {
    & $backendPython "$backendDir\auto-configure-models.py"
} else {
    Write-Host "Python environment not found. Please ensure INDRA setup is complete." -ForegroundColor Red
    exit 1
}

# 2. Start Backend
Write-Host "`n[3/4] Starting backend services (llama-swap and gateway)..." -ForegroundColor Yellow
& "$backendDir\start-backend.ps1"

# Verify backend health
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r1 = Invoke-WebRequest -Uri "http://127.0.0.1:8000/docs" -TimeoutSec 1 -UseBasicParsing -ErrorAction SilentlyContinue
        $r2 = Invoke-WebRequest -Uri "http://127.0.0.1:8100/" -TimeoutSec 1 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($r1.StatusCode -eq 200 -and $r2.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        # Waiting
    }
    Start-Sleep -Milliseconds 500
}

if (-not $ready) {
    Write-Host "Warning: Backend did not respond on ports 8000/8100 within timeout." -ForegroundColor Yellow
} else {
    Write-Host "Backend services are fully operational!" -ForegroundColor Green
}

if (Test-Path "$backendDir\register_models.py") {
    & $backendPython "$backendDir\register_models.py"
}

# 3. Launch Dashboard & Open Browser
Write-Host "`n[4/4] Launching INDRA Dashboard..." -ForegroundColor Yellow

$env:HERMES_HOME = "$rootDir\SIH-26"
$env:DOCKER_CONFIG = "$rootDir\SIH-26\docker-config"
$env:HERMES_NODE = "$rootDir\.indra-runtime\node-v24.11.0-win-x64\node.exe"
if (Test-Path "$rootDir\.indra-runtime\node-v24.11.0-win-x64") {
    $env:PATH = "$rootDir\.indra-runtime\node-v24.11.0-win-x64;$env:PATH"
}

$cudaBinDir = "$backendDir\bin"
if (Test-Path $cudaBinDir) {
    $env:PATH = "$cudaBinDir;$env:PATH"
}

if (Test-Path $indraExe) {
    Write-Host "Opening Dashboard in default browser: http://127.0.0.1:9119" -ForegroundColor Green
    Start-Job -ScriptBlock { 
        Start-Sleep -Seconds 3
        Start-Process "http://127.0.0.1:9119" 
    } | Out-Null
    & $indraExe dashboard --skip-build
} else {
    Write-Host "Frontend CLI (indra.exe) not found in $rootDir\venv\Scripts." -ForegroundColor Red
    exit 1
}
