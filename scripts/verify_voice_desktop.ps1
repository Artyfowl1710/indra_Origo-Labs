# Isolated native renderer acceptance. Cloud/device streams are fixture-controlled.
$ErrorActionPreference='Stop'
$productRoot=Split-Path $PSScriptRoot -Parent
$coreRoot=Join-Path $productRoot 'indra\SIH-26\hermes-agent'
$outputRoot=Join-Path $productRoot 'data\test-results'
$profileRoot=Join-Path $outputRoot ('voice-preview-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $profileRoot | Out-Null
$env:HERMES_HOME=$profileRoot
$env:HERMES_TEST_ISOLATION=$profileRoot
$env:PYTHONUTF8='1'
$env:PYTHONPATH=$productRoot+';'+$coreRoot
foreach($credentialName in @('GEMINI_API_KEY','GOOGLE_API_KEY','OPENROUTER_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY','BASETEN_API_KEY')) {
 [Environment]::SetEnvironmentVariable($credentialName,$null,'Process')
}
# A deterministic loopback provider exercises tool calls without cloud access.
$providerListener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0)
$providerListener.Start();$providerPort=$providerListener.LocalEndpoint.Port;$providerListener.Stop()
$providerOrigin='http://127.0.0.1:'+ $providerPort
$fixtureWorkspace=Join-Path $profileRoot 'sandbox'
New-Item -ItemType Directory -Path $fixtureWorkspace | Out-Null
$settings=@{
 model=@{provider='custom';default='fixture-native';base_url=($providerOrigin+'/v1');context_length=16384;max_tokens=128}
 auxiliary=@{title_generation=@{enabled=$false}}
 security=@{untrusted_content_guard=$true}
 terminal=@{backend='docker';docker_image='indra-documents:1';cwd=$fixtureWorkspace}
 fallback_model=$null
}
# JSON is a valid YAML subset; preserve one configuration loader in the backend.
$settings | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $profileRoot 'config.yaml') -Encoding utf8
'OPENAI_API_KEY=fixture-no-remote-endpoint' | Set-Content -LiteralPath (Join-Path $profileRoot '.env') -Encoding utf8
$listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0)
$listener.Start();$backendPort=$listener.LocalEndpoint.Port;$listener.Stop()
$origin='http://127.0.0.1:'+ $backendPort
$python=Join-Path $productRoot '.indra-python\Scripts\python.exe'
& $python (Join-Path $productRoot 'scripts\seed_usage_fixture.py')
if($LASTEXITCODE -ne 0){throw 'Synthetic usage fixture could not be seeded in the isolated profile.'}
$electron=Join-Path $coreRoot 'apps\desktop\node_modules\electron\dist\electron.exe'
$backend=$null;$preview=$null;$provider=$null
try {
 $providerScript=Join-Path $productRoot 'scripts\chat_title_provider_fixture.py'
 $provider=Start-Process -FilePath $python -ArgumentList @(('"'+$providerScript+'"'),'--port',[string]$providerPort) -WorkingDirectory $productRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $outputRoot 'native-title-provider.log') -RedirectStandardError (Join-Path $outputRoot 'native-title-provider-errors.log')
 $providerReady=$false;$providerDeadline=[DateTime]::UtcNow.AddSeconds(10)
 do {try {if((Invoke-WebRequest -Uri $providerOrigin -UseBasicParsing -TimeoutSec 1).StatusCode -eq 200){$providerReady=$true;break}}catch{};Start-Sleep -Milliseconds 100}while([DateTime]::UtcNow -lt $providerDeadline)
 if(-not $providerReady){throw 'Synthetic loopback provider did not become ready.'}
 $backend=Start-Process -FilePath $python -ArgumentList @('-m','hermes_cli.main','dashboard','--no-open','--skip-build','--host','127.0.0.1','--port',[string]$backendPort) -WorkingDirectory $coreRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $outputRoot 'live-bridge-native-backend.log') -RedirectStandardError (Join-Path $outputRoot 'live-bridge-native-backend-errors.log')
 $ready=$false;$deadline=[DateTime]::UtcNow.AddSeconds(35)
 do {
  if($backend.HasExited){throw 'Isolated fixture backend exited before readiness.'}
  try {$response=Invoke-WebRequest -Uri ($origin+'/chat') -UseBasicParsing -TimeoutSec 1;if($response.StatusCode -eq 200){$ready=$true;break}}catch{}
  Start-Sleep -Milliseconds 200
 }while([DateTime]::UtcNow -lt $deadline)
 if(-not $ready){throw 'Isolated fixture backend did not become ready.'}
 $previewScript=Join-Path $productRoot 'origo-desktop\voice-folder-preview.cjs'
 $preview=Start-Process -FilePath $electron -ArgumentList @(('"'+$previewScript+'"'),'--',$origin) -WorkingDirectory $productRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $outputRoot 'live-bridge-native-renderer.log') -RedirectStandardError (Join-Path $outputRoot 'live-bridge-native-renderer-errors.log')
 if(-not $preview.WaitForExit(120000)){throw 'Native voice/title fixture timed out.'}
 $preview.Refresh()
 if($preview.ExitCode -ne 0){throw 'Native voice fixture reported a failed check. See voice-folder-native-acceptance.json.'}
 $rows=Get-Content -LiteralPath (Join-Path $outputRoot 'voice-folder-native-acceptance.json') -Raw | ConvertFrom-Json
 @{checks=$rows.Count;passed=@($rows | Where-Object {$_.passed -eq $true}).Count;isolated_profile=$true;real_microphone=$false;cloud_inference=$false} | ConvertTo-Json -Compress
} finally {
 # These handles refer only to children created by this fixture, never Indra's
 # normal launcher or a user window. No global process-name termination.
 foreach($owned in @($preview,$backend,$provider)) {
  if($null -ne $owned -and -not $owned.HasExited){Stop-Process -InputObject $owned -ErrorAction SilentlyContinue}
 }
 Remove-Item -LiteralPath (Join-Path $profileRoot '.env') -ErrorAction SilentlyContinue
}
