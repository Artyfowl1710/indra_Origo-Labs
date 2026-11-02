$ErrorActionPreference = 'Stop'
$electron = Join-Path $PSScriptRoot 'indra\SIH-26\hermes-agent\apps\desktop\node_modules\electron\dist\electron.exe'
if (-not (Test-Path $electron)) { throw 'Electron runtime missing.' }
$desktop=Start-Process -FilePath $electron -ArgumentList @((Join-Path $PSScriptRoot 'origo-desktop')) -WorkingDirectory $PSScriptRoot -WindowStyle Normal -PassThru
# Keep the launcher alive for the application lifetime. Managed launch hosts can
# otherwise tear down descendants as soon as the launching shell exits.
$desktop.WaitForExit()
if ($desktop.ExitCode -ne 0) { throw "Indra exited with code $($desktop.ExitCode). See logs/origo-product-backend.log." }
