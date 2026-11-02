param([ValidateSet('child','leaf','escaped')][string]$Role,[string]$Directory)
$ErrorActionPreference='Stop'
function Write-FixtureReceipt([string]$Name,[Diagnostics.Process]$Process) {
 $row=@{pid=$Process.Id;created=($Process.StartTime.ToUniversalTime()-[datetime]'1970-01-01').TotalSeconds}
 $temporary=Join-Path $Directory ($Name+'.tmp')
 $destination=Join-Path $Directory ($Name+'.json')
 [IO.File]::WriteAllText($temporary,($row | ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
 Move-Item -LiteralPath $temporary -Destination $destination -Force
}
Write-FixtureReceipt $Role ([Diagnostics.Process]::GetCurrentProcess())
if ($Role -eq 'child') {
 $deadline=[datetime]::UtcNow.AddSeconds(15)
 while (-not (Test-Path -LiteralPath (Join-Path $Directory 'contained')) -and [datetime]::UtcNow -lt $deadline) {Start-Sleep -Milliseconds 50}
 if (-not (Test-Path -LiteralPath (Join-Path $Directory 'contained'))) {exit 1}
 $arguments=@('-NoProfile','-NonInteractive','-File',('"'+$PSCommandPath+'"'),'leaf',('"'+$Directory+'"'))
 $ownedLeaf=Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -ArgumentList $arguments -WindowStyle Hidden -PassThru
 Write-FixtureReceipt 'leaf-launcher' $ownedLeaf
}
Start-Sleep -Seconds 120
