"""Assemble a self-contained Windows candidate from reviewed public source.

Run after prepare_public_repo.py and author_public_package.py. Never copies a
working user profile, developer venv or inference weights into the release.
"""
from pathlib import Path
import os,shutil,json,hashlib,subprocess,zipfile,tempfile

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT
OUT=ROOT/'release-assets'
BUILD=ROOT/'build'
VERSION='1.8.0-rc.1'
PAYLOAD=Path(tempfile.gettempdir())/'IndraRelease-1.8.0-rc.1'

def copytree(src,dst,extra_ignores=()):
 def native(p):return '\\\\?\\'+str(p.resolve()) if os.name=='nt' else str(p)
 shutil.copytree(native(src),native(dst),dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.pytest_cache','.git',*extra_ignores))

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 if PAYLOAD.exists() and any(PAYLOAD.iterdir()):raise RuntimeError('Use a fresh marked temporary candidate directory; stale payloads are not merged')
 PAYLOAD.mkdir(parents=True,exist_ok=True)
 (PAYLOAD/'.indra-build-marker').write_text('origo-labs-indra-1.8.0-rc.1\n')
 electron=ROOT/'indra/SIH-26/hermes-agent/apps/desktop/node_modules/electron/dist'
 if not (electron/'electron.exe').is_file():electron=ROOT/'indra/SIH-26/hermes-agent/node_modules/electron/dist'
 if not (electron/'electron.exe').is_file():raise RuntimeError('Run npm ci first')
 copytree(electron,PAYLOAD)
 executable=PAYLOAD/'Indra.exe'
 if not executable.exists():os.replace(PAYLOAD/'electron.exe',executable)
 product=PAYLOAD/'resources/app';product.mkdir(parents=True,exist_ok=True)
 # Public source is the sole application source for the bundle.
 for folder in ['origo-desktop','origo_runtime','app','plugins','skills','scripts','docs','docker','examples']:
  copytree(PUBLIC/folder,product/folder)
 if (PUBLIC/'site/index.html').exists():copytree(PUBLIC/'site',product/'guide')
 copytree(PUBLIC/'indra/SIH-26',product/'indra/SIH-26',extra_ignores=('website','web','apps','tests','tests-js','ui-tui','docs'))
 core=product/'indra/SIH-26/hermes-agent'
 copytree(ROOT/'indra/SIH-26/hermes-agent/hermes_cli/web_dist',core/'hermes_cli/web_dist')
 bridge=ROOT/'indra/SIH-26/hermes-agent/scripts/whatsapp-bridge/node_modules'
 if bridge.exists():copytree(bridge,core/'scripts/whatsapp-bridge/node_modules')
 for name in ['SOUL.md','TOOLS.md','VERSION','LICENSE','NOTICE.md','requirements-release.txt']:
  shutil.copyfile(PUBLIC/name,product/name)
 (product/'package.json').write_text(json.dumps({'name':'indra-origo-labs','productName':'Indra','version':VERSION,'main':'origo-desktop/entry.cjs','private':True},indent=2))
 runtime=product/'runtime/python'
 copytree(BUILD/'release-tools/python-3.13.17-embed-amd64',runtime)
 copytree(BUILD/'release-python-packages',runtime/'Lib/site-packages')
 (runtime/'python313._pth').write_text('python313.zip\n.\nLib\nLib/site-packages\nLib/site-packages/win32\nLib/site-packages/win32/lib\nLib/site-packages/Pythonwin\n../..\n../../indra/SIH-26\n../../indra/SIH-26/hermes-agent\nimport site\n')
 # Embedded Python ignores registry configuration; pywin32 DLLs need an explicit search directory.
 (runtime/'Lib/site-packages/sitecustomize.py').write_text('import os, pathlib, sys\nsys.path.insert(0,str(pathlib.Path(sys.executable).parents[2]))\n# Restore standard Python CLI project imports while keeping the backend cwd controlled.\n_arg=sys.argv[0] if sys.argv else ""\n_project=pathlib.Path(_arg).resolve().parent if _arg not in ("", "-", "-c", "-m") else pathlib.Path.cwd()\nsys.path.insert(0,str(_project))\n_dll_handles=[]\np=pathlib.Path(__file__).parent/"pywin32_system32"\nif p.is_dir() and hasattr(os,"add_dll_directory"):_dll_handles.append(os.add_dll_directory(str(p)))\n')
 node=product/'runtime/node';node.mkdir(parents=True,exist_ok=True)
 node_exe=Path(shutil.which('node'))
 shutil.copyfile(node_exe,node/'node.exe')
 for name in ['LICENSE','LICENSE.txt']:
  if (node_exe.parent/name).is_file():shutil.copyfile(node_exe.parent/name,node/'LICENSE.txt');break
 if not (node/'LICENSE.txt').exists():(node/'LICENSE.txt').write_text(subprocess.check_output([str(node_exe),'--license'],text=True,encoding='utf-8'),encoding='utf-8')
 model=product/'data/models/minilm'
 copytree(ROOT/'data/models/minilm',model)
 # Files fetched from upstream with their license/provenance by the preparation step.
 for name in ['LICENSE','MODEL_CARD.md']:
  if (BUILD/'release-model-notices'/name).exists():shutil.copyfile(BUILD/'release-model-notices'/name,model/name)
 if not (model/'LICENSE').exists():raise RuntimeError('MiniLM model license required')
 (PAYLOAD/'Indra-CLI.cmd').write_text('@echo off\nset "HERMES_HOME=%LOCALAPPDATA%\\OrigoLabs\\Indra\\profile"\nset "PATH=%~dp0resources\\app\\runtime\\python;%~dp0resources\\app\\runtime\\node;%PATH%"\n"%~dp0resources\\app\\runtime\\python\\python.exe" -m hermes_cli.main %*\n',encoding='utf-8')
 (PAYLOAD/'README.txt').write_text('Indra - Origo Labs / Windows x64 release candidate '+VERSION+'\n\nOpen Indra.exe. Add your own provider key or local endpoint.\nState is stored in LocalAppData/OrigoLabs/Indra, not this folder.\nThis candidate is unsigned and needs an independent second-PC acceptance test.\nNo API keys, chat history, paired phone accounts or large inference weights are included.\nOffline handbook: resources/app/docs/handbook/index.md\n',encoding='utf-8')
 report=json.loads((BUILD/'release-pip-report.json').read_text(encoding='utf-8'))
 dependencies=sorted([{'name':x['metadata']['name'],'version':x['metadata']['version'],'archive_sha256':x.get('download_info',{}).get('archive_info',{}).get('hashes',{}).get('sha256')} for x in report['install']],key=lambda x:x['name'].lower())
 manifest={'version':VERSION,'platform':'windows-x64','python':'3.13.17','electron':json.loads((electron.parent/'package.json').read_text())['version'],'node':subprocess.check_output([str(node_exe),'--version'],text=True).strip(),'python_dependencies':dependencies,'private_profile_included':False,'large_inference_models_included':False}
 (PUBLIC/'provenance/runtime-dependencies.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (product/'runtime-dependencies.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (PUBLIC/'requirements-release.lock.txt').write_text('\n'.join(f"{x['name']}=={x['version']}" for x in dependencies)+'\n')
 # NSIS compiler uses a fixed per-user installation directory and a marker guard.
 nsis=BUILD/'release-tools/nsis/nsis-3.12/makensis.exe'
 if not nsis.exists():nsis=next((BUILD/'release-tools/nsis').rglob('makensis.exe'))
 installer=OUT/f'Indra-Setup-{VERSION}.exe'
 spec=BUILD/'Indra-Setup.nsi'
 spec.write_text(r'''
Unicode true
!include "MUI2.nsh"
Name "Indra · Origo Labs"
OutFile "@OUT@"
InstallDir "$LOCALAPPDATA\Programs\OrigoLabs\Indra"
RequestExecutionLevel user
SetCompressor zlib
VIProductVersion "1.8.0.0"
VIAddVersionKey "ProductName" "Indra"
VIAddVersionKey "CompanyName" "Origo Labs"
VIAddVersionKey "FileDescription" "Indra Windows release candidate installer"
VIAddVersionKey "FileVersion" "1.8.0-rc.1"
VIAddVersionKey "LegalCopyright" "Origo Labs and respective upstream contributors"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "@LICENSE@"
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\Indra.exe"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
Function .onInit
  IfFileExists "$INSTDIR\Indra.exe" 0 done
  MessageBox MB_OKCANCEL "Close any running Indra window before updating this installation. Your profile will be preserved." IDOK done
  Abort
  done:
FunctionEnd
Section "Indra"
  SetOutPath "$INSTDIR"
  File /r "@PAYLOAD@\*.*"
  FileOpen $0 "$INSTDIR\.indra-install-marker" w
  FileWrite $0 "origo-labs-indra-1"
  FileClose $0
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\Origo Labs"
  CreateShortcut "$SMPROGRAMS\Origo Labs\Indra.lnk" "$INSTDIR\Indra.exe"
  CreateShortcut "$SMPROGRAMS\Origo Labs\Indra Guide.lnk" "$INSTDIR\resources\app\guide\index.html"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\IndraOrigoLabs" "DisplayName" "Indra · Origo Labs"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\IndraOrigoLabs" "DisplayVersion" "1.8.0-rc.1"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\IndraOrigoLabs" "Publisher" "Origo Labs"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\IndraOrigoLabs" "UninstallString" '"$INSTDIR\Uninstall.exe"'
SectionEnd
Section "Uninstall"
  StrCmp $INSTDIR "$LOCALAPPDATA\Programs\OrigoLabs\Indra" 0 unsafe
  FileOpen $0 "$INSTDIR\.indra-install-marker" r
  IfErrors unsafe
  FileRead $0 $1
  FileClose $0
  StrCmp $1 "origo-labs-indra-1" 0 unsafe
  Delete "$SMPROGRAMS\Origo Labs\Indra.lnk"
  Delete "$SMPROGRAMS\Origo Labs\Indra Guide.lnk"
  RMDir "$SMPROGRAMS\Origo Labs"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\IndraOrigoLabs"
  RMDir /r "$INSTDIR"
  Goto finished
  unsafe:
  MessageBox MB_ICONSTOP "Installation marker or location did not match. No files were removed."
  finished:
SectionEnd
'''.replace('@OUT@',str(installer)).replace('@LICENSE@',str(PUBLIC/'LICENSE')).replace('@PAYLOAD@',str(PAYLOAD)),encoding='utf-8')
 subprocess.run([str(nsis),'/V2',str(spec)],check=True)
 archive=OUT/f'Indra-{VERSION}-windows-x64-portable.zip'
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in PAYLOAD.rglob('*'):
   if p.is_file():z.write(p,Path(PAYLOAD.name)/p.relative_to(PAYLOAD))
 video=ROOT/'deliverables/Indra-real-demo/Indra-real-footage-3min.mp4'
 if video.exists():shutil.copyfile(video,OUT/video.name)
 for name in ['English-voiceover.txt','English-voiceover.srt','EDIT-NOTES.txt']:
  if (video.parent/name).exists():shutil.copyfile(video.parent/name,OUT/name)
 hashes=[]
 for p in sorted(OUT.iterdir()):
  if p.is_file() and p.name!='SHA256SUMS.txt':hashes.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name)
 (OUT/'SHA256SUMS.txt').write_text('\n'.join(hashes)+'\n')
 print(json.dumps({'payload':str(PAYLOAD),'release_assets':[{'name':p.name,'bytes':p.stat().st_size} for p in OUT.iterdir() if p.is_file()]},indent=2))

if __name__=='__main__':main()
