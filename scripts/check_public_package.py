"""Fail closed on common secret/runtime artifacts and broken current-doc links.

Print locations/types only, never matched credential values. This scanner is
defense in depth, not an independent security audit.
"""
from pathlib import Path
import re,json,os,sys,hashlib
ROOT=Path(__file__).resolve().parents[1]
PATTERNS={
 'openrouter_key':re.compile(r'sk-or-v1-[A-Za-z0-9]{40,}'),
 'provider_key':re.compile(r'(?<![A-Za-z0-9])(?:sk-proj-|sk-ant-api\d+-|AIza)[A-Za-z0-9_-]{28,}'),
 'telegram_token':re.compile(r'(?<!\d)\d{8,12}:[A-Za-z0-9_-]{30,}'),
 'github_token':re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})'),
 'private_key':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----')}
SKIP={'.git','node_modules','site','__pycache__','.venv','.indra-python','build','.pytest_cache','.pytest-cache'}

def files():
 for directory,dirs,names in os.walk(ROOT):
  dirs[:]=[x for x in dirs if x not in SKIP]
  for name in names:yield Path(directory)/name

def main():
 findings=[];count=total=0
 allowfile=ROOT/'provenance/synthetic-secret-fixtures.json'
 allowed=json.loads(allowfile.read_text(encoding='utf-8')) if allowfile.exists() else []
 reviewed={(x['path'],x['kind'],x['sha256']) for x in allowed}
 for p in files():
  rel=p.relative_to(ROOT).as_posix()
  rawpath='\\\\?\\'+str(p.resolve()) if os.name=='nt' else str(p)
  try:blob=open(rawpath,'rb').read()
  except OSError:findings.append({'path':rel,'kind':'unreadable'});continue
  count+=1;total+=len(blob)
  if blob[:4]==b'\x7fELF' or blob[:2]==b'MZ':findings.append({'path':rel,'kind':'compiled_executable_in_source'})
  if len(blob)>=100*1024*1024:findings.append({'path':rel,'kind':'github_file_limit'})
  if p.name=='.env' or (p.name.startswith('.env.') and p.name not in {'.env.example','.env.sample','.env.template'}):findings.append({'path':rel,'kind':'environment_file'})
  if p.suffix.lower() in {'.sqlite','.sqlite3','.db','.key','.pfx','.p12','.keystore','.gguf','.safetensors','.onnx','.exe','.dll','.pyd'}:findings.append({'path':rel,'kind':'runtime_or_secret_file'})
  if b'\0' in blob[:8192] or len(blob)>8*1024*1024:continue
  text=blob.decode('utf-8',errors='replace')
  for kind,pattern in PATTERNS.items():
   for m in pattern.finditer(text):
    if (rel,kind,hashlib.sha256(m.group(0).encode()).hexdigest()) in reviewed:continue
    # Published synthetic fixtures deliberately use low-entropy dummy keys.
    if kind!='private_key' and len(set(m.group(0).split(':')[-1].split('-')[-1]))<9:continue
    # Explicit private-key fixtures are reviewed source test vectors, not user signing state.
    if kind=='private_key' and any(x in p.parts for x in ['tests','fixtures','test-fixtures']):continue
    findings.append({'path':rel,'line':text.count('\n',0,m.start())+1,'kind':kind})
 # Current product docs are authoritative; imported/historical docs have separate upstream scope.
 docs=[ROOT/'README.md',ROOT/'HACKATHON.md',ROOT/'NOTICE.md']+list((ROOT/'docs/handbook').glob('*.md'))
 for p in docs:
  text=p.read_text(encoding='utf-8')
  for match in re.finditer(r'!?\[[^\]]*\]\(([^)]+)\)',text):
   url=match.group(1).split('#')[0].split(' "')[0]
   if not url or re.match(r'^(https?:|mailto:|#)',url):continue
   if not (p.parent/url).exists():findings.append({'path':p.relative_to(ROOT).as_posix(),'kind':'broken_link','target':url})
 report={'ok':not findings,'files':count,'bytes':total,'findings':findings,'scope':'source files and current handbook; private runtime excluded; synthetic key fixtures reviewed separately'}
 print(json.dumps(report,indent=2))
 return 0 if report['ok'] else 1

if __name__=='__main__':sys.exit(main())
