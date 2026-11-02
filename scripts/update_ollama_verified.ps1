$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$installer = Join-Path $root 'data\runtime-downloads\OllamaSetup-0.40.13.exe'
$release = Get-Content (Join-Path $root 'data\runtime-downloads\ollama-release.json') -Raw | ConvertFrom-Json
if ((Get-Item -LiteralPath $installer).Length -ne $release.bytes) { throw 'Installer download is incomplete.' }
$actual = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
if ('sha256:' + $actual -ne $release.expected_digest) { throw 'Official installer hash mismatch.' }
$signature = Get-AuthenticodeSignature -LiteralPath $installer
if ($signature.Status -ne 'Valid') { throw 'Installer signature is not valid.' }
Write-Output "Verified installer signer: $($signature.SignerCertificate.Subject)"
$owned = Get-Process -Id 32776 -ErrorAction SilentlyContinue
$expected = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
if ($owned -and $owned.Path -eq $expected) { Stop-Process -Id $owned.Id }
$install = Start-Process -FilePath $installer -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') -PassThru -WindowStyle Hidden
$install.WaitForExit()
Write-Output "Installer exit code: $($install.ExitCode)"
if ($install.ExitCode -ne 0) { throw 'Ollama installation did not complete successfully.' }
