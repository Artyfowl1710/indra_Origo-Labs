$ErrorActionPreference='Stop'
$productRoot=Split-Path $PSScriptRoot -Parent
$core=Join-Path $productRoot 'indra\SIH-26\hermes-agent'
$output=Join-Path $productRoot ('data\test-results\theme-channels-'+[guid]::NewGuid().ToString('N'))
$homePath=Join-Path $output 'home'
New-Item -ItemType Directory -Path $homePath -Force | Out-Null
$env:HERMES_HOME=$homePath
$env:HERMES_DESKTOP='1'
$env:PYTHONUTF8='1'
foreach($name in @('GEMINI_API_KEY','GOOGLE_API_KEY','OPENAI_API_KEY','OPENROUTER_API_KEY','BASETEN_API_KEY','TELEGRAM_BOT_TOKEN','DISCORD_BOT_TOKEN')){
 [Environment]::SetEnvironmentVariable($name,$null,'Process')
}
@{
 model=@{provider='custom';default='fixture-text';base_url='http://127.0.0.1:1/v1'}
 terminal=@{backend='docker';cwd=$homePath}
 security=@{untrusted_content_guard=$true}
 delegation=@{max_concurrent_children=3;subagent_auto_approve=$false}
 fallback_model=$null
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $homePath 'config.yaml') -Encoding utf8
$listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0)
$listener.Start();$port=$listener.LocalEndpoint.Port;$listener.Stop()
$origin='http://127.0.0.1:'+$port
$backend=$null
try{
 $python=Join-Path $productRoot '.indra-python\Scripts\python.exe'
 $backend=Start-Process -FilePath $python -ArgumentList @('-m','hermes_cli.main','dashboard','--no-open','--skip-build','--host','127.0.0.1','--port',[string]$port) -WorkingDirectory $core -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $output 'backend.log') -RedirectStandardError (Join-Path $output 'backend-errors.log')
 $ready=$false;$deadline=[DateTime]::UtcNow.AddSeconds(40)
 do{
  if($backend.HasExited){throw 'Fixture backend exited.'}
  try{if((Invoke-WebRequest -Uri ($origin+'/overview') -UseBasicParsing -TimeoutSec 1).StatusCode -eq 200){$ready=$true;break}}catch{}
  Start-Sleep -Milliseconds 200
 }while([DateTime]::UtcNow -lt $deadline)
 if(-not $ready){throw 'Fixture backend did not become ready.'}
 $electron=Join-Path $core 'apps\desktop\node_modules\electron\dist\electron.exe'
 $script=Join-Path $productRoot 'origo-desktop\acceptance-app'
 $preview=Start-Process -FilePath $electron -ArgumentList @('--disable-gpu',('"'+$script+'"'),$origin,('"'+$output+'"')) -WorkingDirectory $productRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $output 'electron.log') -RedirectStandardError (Join-Path $output 'electron-errors.log')
 if(-not $preview.WaitForExit(240000)){$preview.Kill();throw 'Native acceptance timed out.'}
 $report=Join-Path $output 'acceptance.json'
 if(-not (Test-Path -LiteralPath $report)){throw "Electron exited $($preview.ExitCode); inspect $output"}
 $checks=@(Get-Content -LiteralPath $report -Raw | ConvertFrom-Json)
 @{output=$output;checks=$checks} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $productRoot 'data\test-results\theme-channels-acceptance.json') -Encoding utf8
 if($checks.Where({-not $_.passed}).Count){throw "Native acceptance failed; inspect $report"}
 Write-Output "Passed $($checks.Count) native checks. Output: $output"
}finally{if($backend -and -not $backend.HasExited){Stop-Process -InputObject $backend}}
