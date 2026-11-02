<#
.SYNOPSIS
One-click Execution Backend Switcher for INDRA (Local Host <-> Docker Sandbox)

.DESCRIPTION
Switches INDRA agent execution backend between Native Local and Docker Sandbox (indra-documents:1).
Usage:
  .\switch-backend.ps1 docker   # Switches to Docker isolated sandbox
  .\switch-backend.ps1 local    # Switches to Native Local Host execution
  .\switch-backend.ps1 status   # Checks current backend setting and container readiness
#>

param(
    [ValidateSet("docker", "local", "status")]
    [string]$Mode = "status"
)

$ErrorActionPreference = 'Stop'
$rootDir = $PSScriptRoot
$configPath = "$rootDir\SIH-26\config.yaml"

if (-not (Test-Path $configPath)) {
    Write-Host "Error: config.yaml not found at $configPath" -ForegroundColor Red
    exit 1
}

$content = Get-Content -Path $configPath -Raw

if ($Mode -eq "status") {
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "       INDRA EXECUTION BACKEND STATUS     " -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    
    if ($content -match "backend:\s*(docker|local)") {
        $current = $matches[1]
        Write-Host "Active Backend in config.yaml: " -NoNewline
        if ($current -eq "docker") {
            Write-Host "DOCKER SANDBOX (indra-documents:1)" -ForegroundColor Green
        } else {
            Write-Host "LOCAL HOST (Native Windows)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "Active Backend: Unknown (defaults to local)" -ForegroundColor Gray
    }
    
    # Check Docker daemon
    Write-Host "`nDocker Readiness Check:" -ForegroundColor Cyan
    $dockerVer = docker info --format "{{.ServerVersion}}" 2>$null
    if ($dockerVer) {
        Write-Host "  [OK] Docker Daemon is active (v$dockerVer)" -ForegroundColor Green
        $hasImage = docker images -q indra-documents:1 2>$null
        if ($hasImage) {
            Write-Host "  [OK] Sandbox Image 'indra-documents:1' is built and ready" -ForegroundColor Green
        } else {
            Write-Host "  [!] Sandbox Image 'indra-documents:1' is not found." -ForegroundColor Yellow
        }
    } else {
        Write-Host "  [!] Docker Daemon is not responding or Docker Desktop is off." -ForegroundColor Red
    }
    
    Write-Host "`nTo switch backend:"
    Write-Host "  .\switch-backend.ps1 docker  (or via UI at http://127.0.0.1:9119/sandbox)" -ForegroundColor Gray
    Write-Host "  .\switch-backend.ps1 local" -ForegroundColor Gray
    exit 0
}

if ($Mode -eq "docker") {
    # Verify Docker is running
    $dockerCheck = docker info --format "{{.ServerVersion}}" 2>$null
    if (-not $dockerCheck) {
        Write-Host "Error: Docker daemon is not running. Please start Docker Desktop first." -ForegroundColor Red
        exit 1
    }
    $hasImage = docker images -q indra-documents:1 2>$null
    if (-not $hasImage) {
        Write-Host "Error: indra-documents:1 image not found in local Docker. Please build it first." -ForegroundColor Red
        exit 1
    }
    
    # Replace backend: local with backend: docker
    $newContent = $content -replace "backend:\s*local", "backend: docker"
    Set-Content -Path $configPath -Value $newContent -NoNewline
    Write-Host "`n[SUCCESS] INDRA Execution Backend switched to: DOCKER SANDBOX (indra-documents:1)" -ForegroundColor Green
    Write-Host "Agent tool and code execution will now run fully isolated in the Docker container." -ForegroundColor Cyan
    Write-Host "All output artifacts will continue to synchronize to ./outputs/ for instant frontend preview." -ForegroundColor Cyan
}

if ($Mode -eq "local") {
    $newContent = $content -replace "backend:\s*docker", "backend: local"
    Set-Content -Path $configPath -Value $newContent -NoNewline
    Write-Host "`n[SUCCESS] INDRA Execution Backend switched to: LOCAL HOST (Native Windows)" -ForegroundColor Green
    Write-Host "Agent tool and code execution will now run directly on the host machine." -ForegroundColor Cyan
}
