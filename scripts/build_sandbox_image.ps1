$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Dockerfile = Join-Path $ProjectRoot 'docker\Dockerfile.dev-sandbox'
if (-not (Test-Path $Dockerfile)) { throw "Sandbox Dockerfile missing: $Dockerfile" }
$Docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $Docker) { throw 'Docker CLI was not found. Install Docker Desktop and reopen PowerShell.' }
& docker info --format '{{.ServerVersion}}' *> $null
if ($LASTEXITCODE -ne 0) { throw 'Docker daemon is unavailable. Start Docker Desktop, then retry.' }
Write-Host ''
Write-Host 'This will build indra-sandbox:dev from docker/Dockerfile.dev-sandbox.' -ForegroundColor Cyan
Write-Host 'Docker may download a base image and OS/Python packages from the internet.' -ForegroundColor Yellow
Write-Host 'The build context is the docker folder only; your workspace and .env are not sent.' -ForegroundColor Green
$answer = Read-Host 'Type BUILD to approve these downloads and build the image'
if ($answer -cne 'BUILD') { Write-Host 'Cancelled; no image build was started.'; exit 0 }
Push-Location (Join-Path $ProjectRoot 'docker')
try {
  & docker build --pull -f Dockerfile.dev-sandbox -t indra-sandbox:dev .
  if ($LASTEXITCODE -ne 0) { throw 'Docker image build failed. Review the first failing package/build message above.' }
}
finally { Pop-Location }
Write-Host ''
Write-Host 'Built indra-sandbox:dev.' -ForegroundColor Green
Write-Host 'Set INDRA_SANDBOX_IMAGE=indra-sandbox:dev in .env, then restart Indra Origo.'
Write-Host 'This image provides common Python/Node/Git tooling, not every dependency of every project.'
