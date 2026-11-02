param(
 [string]$JavaHome=$env:JAVA_HOME,
 [string]$AndroidSdk=$env:ANDROID_HOME,
 [switch]$Offline
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$project=Join-Path $root 'android\OrigoRemote'
if (-not $JavaHome) {$JavaHome=Join-Path $env:ProgramFiles 'Android\Android Studio\jbr'}
if (-not $AndroidSdk) {$AndroidSdk=Join-Path $env:LOCALAPPDATA 'Android\Sdk'}
if (-not (Test-Path -LiteralPath (Join-Path $JavaHome 'bin\java.exe'))) {throw 'Set -JavaHome to a JDK 17+ installation.'}
if (-not (Test-Path -LiteralPath (Join-Path $AndroidSdk 'platforms\android-35\android.jar'))) {throw 'Install Android SDK platform 35 and pass its SDK directory with -AndroidSdk.'}
$wrapper=Join-Path $project 'gradlew.bat'
if (-not (Test-Path -LiteralPath $wrapper)) {throw 'The Android Gradle wrapper is missing from the project.'}
$env:JAVA_HOME=$JavaHome
$env:ANDROID_HOME=$AndroidSdk
$env:ANDROID_USER_HOME=Join-Path $project '.android-user'
$env:GRADLE_USER_HOME=Join-Path $project '.gradle-user'
$arguments=@('--no-daemon','--console=plain','--project-cache-dir','.gradle-project','testDebugUnitTest','assembleDebug')
if ($Offline) {$arguments=@('--offline')+$arguments}
Push-Location $project
try {
 & $wrapper @arguments 2>&1 | Tee-Object -FilePath (Join-Path $project 'build-verification.log')
 if ($LASTEXITCODE -ne 0) {throw 'Android build/tests failed. Inspect android/OrigoRemote/build-verification.log.'}
 $apk=Join-Path $project 'app\build\outputs\apk\debug\app-debug.apk'
 $tools=Get-ChildItem -LiteralPath (Join-Path $AndroidSdk 'build-tools') -Directory | Where-Object {$_.Name -match '^\d+\.\d+\.\d+$'} | Sort-Object {[version]$_.Name} -Descending | Select-Object -First 1
 if (-not $tools) {throw 'Install Android SDK build tools to verify the APK signature.'}
 & (Join-Path $tools.FullName 'apksigner.bat') verify --verbose $apk
 if ($LASTEXITCODE -ne 0) {throw 'APK signature verification failed.'}
 $distribution=Join-Path $root 'dist'
 New-Item -ItemType Directory -Force -Path $distribution | Out-Null
 $destination=Join-Path $distribution 'OrigoRemote-1.1.0-debug.apk'
 Copy-Item -LiteralPath $apk -Destination $destination -Force
 $hash=(Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
 [IO.File]::WriteAllText(($destination+'.sha256'),($hash+'  '+[IO.Path]::GetFileName($destination)+[Environment]::NewLine),[Text.UTF8Encoding]::new($false))
 Write-Output "Built and verified: $destination"
 Write-Output "SHA-256: $hash"
 Write-Output 'This is a personal-test debug APK. Device pairing and microphone/file-picker acceptance require runtime testing.'
} finally {Pop-Location}
