param(
 [ValidatePattern('^http://127\.0\.0\.1:\d+$')][string]$Origin,
 [ValidatePattern('^[A-Za-z0-9_.:-]{1,240}$')][string]$Chat,
 [ValidatePattern('^[A-Za-z0-9_.:-]{1,240}$')][string]$RequestId,
 [ValidatePattern('^[a-f0-9]{32}$')][string]$Nonce
)
$ErrorActionPreference='Stop'
$reviewRoot=Split-Path $PSScriptRoot -Parent
$reviewElectron=Join-Path $reviewRoot 'indra/SIH-26/hermes-agent/apps/desktop/node_modules/electron/dist/electron.exe'
$reviewScript='origo-desktop/content-guard-preview.cjs'
# Separate URL data from Electron switches on Windows.
$reviewProcess=Start-Process -FilePath $reviewElectron -ArgumentList @($reviewScript,'--',$Origin,$Chat,$RequestId) -WorkingDirectory $reviewRoot -WindowStyle Hidden -PassThru -RedirectStandardError (Join-Path $reviewRoot 'data/test-results/native-review-stderr.log') -RedirectStandardOutput (Join-Path $reviewRoot 'data/test-results/native-review-stdout.log')
$reviewProcess.WaitForExit()
if ($Nonce) {
 $reviewReceipt=Join-Path $reviewRoot 'data/test-results/real-project-goal-guarded/native-review-response.json'
 @{nonce=$Nonce;passed=($reviewProcess.ExitCode -eq 0);exit_code=$reviewProcess.ExitCode} | ConvertTo-Json | Set-Content -LiteralPath $reviewReceipt -Encoding UTF8
}
exit $reviewProcess.ExitCode
