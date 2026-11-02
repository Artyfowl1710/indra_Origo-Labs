param([Parameter(Mandatory=$true)][string]$Origin,[Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference='Stop'
$productRoot=Split-Path $PSScriptRoot -Parent
$electron=Join-Path $productRoot 'indra\SIH-26\hermes-agent\apps\desktop\node_modules\electron\dist\electron.exe'
$script=Join-Path $productRoot 'origo-desktop\theme-channels-preview.cjs'
$child=Start-Process -FilePath $electron -ArgumentList @(('"'+$script+'"'),$Origin,('"'+$OutputDirectory+'"')) -WorkingDirectory $productRoot -WindowStyle Hidden -PassThru -Wait
exit $child.ExitCode
