<#
.SYNOPSIS
One-click stop script for all INDRA services and ports.

.DESCRIPTION
Stops the INDRA Gateway (8000), llama-swap (8100), INDRA Dashboard (9119),
and any background llama-server processes.
#>

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "           STOPPING INDRA SYSTEM          " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Stop llama inference processes
Write-Host "`nStopping llama-server and llama-swap..." -ForegroundColor Yellow
Get-Process | Where-Object { 
    $_.ProcessName -match "llama-server|llama-swap" 
} | Stop-Process -Force -ErrorAction SilentlyContinue

# 2. Stop processes on INDRA ports
$ports = 8000, 8100, 9119
foreach ($port in $ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($conn in $connections) {
            try {
                $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
                if ($proc) {
                    Write-Host "Stopping process $($proc.ProcessName) (PID: $($proc.Id)) on port $port..." -ForegroundColor Yellow
                    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                }
            } catch {
                # Ignore
            }
        }
    }
}

Start-Sleep -Seconds 1

# 3. Verify ports are free
$allFree = $true
foreach ($port in $ports) {
    $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conn) {
        Write-Host "Warning: Port $port is still in use." -ForegroundColor Red
        $allFree = $false
    }
}

if ($allFree) {
    Write-Host "`n[SUCCESS] All INDRA services and ports (8000, 8100, 9119) are closed." -ForegroundColor Green
} else {
    Write-Host "`n[WARN] Some ports could not be released immediately." -ForegroundColor Yellow
}
