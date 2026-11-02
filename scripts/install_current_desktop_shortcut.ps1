# Point the installed app shortcut at this prepared native integration build.
$ErrorActionPreference='Stop'
$productRoot=Split-Path $PSScriptRoot -Parent
$launcher=Join-Path $productRoot 'start_origo_auto.ps1'
foreach($required in @($launcher,(Join-Path $productRoot '.indra-python\Scripts\python.exe'),(Join-Path $productRoot 'origo-desktop\entry.cjs'),(Join-Path $productRoot 'indra\SIH-26\hermes-agent\apps\desktop\node_modules\electron\dist\electron.exe'))){
 if(-not(Test-Path -LiteralPath $required -PathType Leaf)){throw 'The prepared Indra desktop build is incomplete.'}
}
$programs=[Environment]::GetFolderPath('Programs')
$shortcutPath=Join-Path $programs 'Indra Origo.lnk'
if(Test-Path -LiteralPath $shortcutPath){
 $backup=Join-Path $productRoot ('data\shortcut-backups\'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff'))
 New-Item -ItemType Directory -Path $backup -Force | Out-Null
 Copy-Item -LiteralPath $shortcutPath -Destination $backup
}
$shell=New-Object -ComObject WScript.Shell
$shortcut=$shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$shortcut.Arguments='-NoProfile -WindowStyle Hidden -File "'+$launcher+'"'
$shortcut.WorkingDirectory=$productRoot
$shortcut.Description='Indra · Origo Labs — native workspace'
$shortcut.WindowStyle=7
$shortcut.Save()
$verified=$shell.CreateShortcut($shortcutPath)
if($verified.Arguments -ne $shortcut.Arguments -or $verified.WorkingDirectory -ne $productRoot){throw 'Shortcut verification failed.'}
Write-Output 'Indra Origo Start menu shortcut now opens the current native build.'
