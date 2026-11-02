"""Fetch verified build tools and install fresh locked Windows dependencies."""
from pathlib import Path
import sys,struct,hashlib,json,shutil,subprocess,zipfile,time
import httpx

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build'

def download(url,destination,expected=None):
 destination.parent.mkdir(parents=True,exist_ok=True)
 if destination.exists() and expected and hashlib.sha256(destination.read_bytes()).hexdigest()==expected:return
 last=None
 for attempt in range(3):
  try:
   with httpx.Client(follow_redirects=True,timeout=90,trust_env=False) as client:
    with client.stream('GET',url) as response:
     response.raise_for_status();temporary=destination.with_suffix(destination.suffix+'.part');digest=hashlib.sha256()
     with temporary.open('wb') as stream:
      for block in response.iter_bytes():digest.update(block);stream.write(block)
   if expected and digest.hexdigest()!=expected:raise ValueError('SHA-256 mismatch: '+destination.name)
   temporary.replace(destination);return
  except (httpx.HTTPError,OSError) as error:last=error;time.sleep(attempt+1)
 raise RuntimeError('Verified download failed: '+destination.name) from last

def extract(archive,target):
 with zipfile.ZipFile(archive) as z:
  for info in z.infolist():
   if not (target/info.filename).resolve().is_relative_to(target.resolve()):raise ValueError('Unsafe archive path')
  z.extractall(target)

def main():
 if sys.platform!='win32' or sys.version_info[:2]!=(3,13) or struct.calcsize('P')!=8:raise SystemExit('Use Windows x64 Python 3.13 in a dedicated build environment')
 tools=BUILD/'release-tools';tools.mkdir(parents=True,exist_ok=True)
 py=tools/'python-3.13.17-embed-amd64.zip'
 download('https://www.python.org/ftp/python/3.13.17/'+py.name,py,'9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38')
 extract(py,tools/py.stem)
 nsis=tools/'nsis-3.12.zip'
 download('https://downloads.sourceforge.net/project/nsis/NSIS%203/3.12/nsis-3.12.zip',nsis,'56581f90db321581c5381193d796fffcf2d24b2f8fed2160a6c6a3baa67f2c4f')
 extract(nsis,tools/'nsis')
 target=BUILD/'release-python-packages'
 if target.exists():raise SystemExit('Use a fresh build/release-python-packages directory; stale packages are not merged')
 subprocess.run([sys.executable,'-m','pip','install','--ignore-installed','--target',str(target),'--no-compile','--only-binary=:all:','--report',str(BUILD/'release-pip-report.json'),'-r',str(ROOT/'requirements-release.lock.txt')],check=True)
 manifest=json.loads((ROOT/'packaging/minilm-manifest.json').read_text(encoding='utf-8'));model=ROOT/'data/models/minilm'
 for filename,metadata in manifest['files'].items():
  remote='onnx/'+filename if filename.endswith('.onnx') else filename
  download(f"https://huggingface.co/{manifest['repository']}/resolve/{manifest['revision']}/{remote}",model/filename,metadata['sha256'])
 (model/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 notices=BUILD/'release-model-notices';notices.mkdir(exist_ok=True)
 shutil.copyfile(ROOT/'packaging/licenses/MiniLM-Apache-2.0.txt',notices/'LICENSE')
 shutil.copyfile(ROOT/'packaging/licenses/MiniLM-NOTICE.txt',notices/'MODEL_CARD.md')
 print('Build inputs verified. Build the workbench and WhatsApp bridge, then run packaging/build_windows.py.')

if __name__=='__main__':main()
