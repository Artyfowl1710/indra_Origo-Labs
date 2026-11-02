from pathlib import Path
import struct,hashlib,json
folder=Path(r'C:\Users\khatr\OneDrive\Desktop\SIH-26-main\SIH-26\hermes-agent\backend\models')
formats={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
rows=[]
for p in sorted(folder.glob('*.gguf')):
 with p.open('rb') as f:
  def scalar(fmt):return struct.unpack('<'+fmt,f.read(struct.calcsize(fmt)))[0]
  def string(keep=True):
   length=scalar('Q')
   if length>100_000_000:raise ValueError('invalid string length')
   if keep:return f.read(length).decode('utf-8',errors='replace')
   f.seek(length,1)
  def value(t,keep=True):
   if t==8:return string(keep)
   if t==9:
    subtype=scalar('I');count=scalar('Q')
    if count>10_000_000:raise ValueError('invalid array length')
    for _ in range(count):value(subtype,False)
    return {'array_items':count}
   if t not in formats:raise ValueError('invalid metadata type')
   return scalar(formats[t])
  magic=f.read(4);version=scalar('I');tensors=scalar('Q');count=scalar('Q');meta={}
  if magic!=b'GGUF' or version not in (2,3) or count>100000:raise ValueError('invalid GGUF')
  for _ in range(count):
   key=string();t=scalar('I');keep=not key.startswith('tokenizer.')
   v=value(t,keep)
   if keep:meta[key]=v
 digest=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
 row={'file':p.name,'bytes':p.stat().st_size,'version':version,'tensors':tensors,'sha256':digest,'metadata':meta};rows.append(row)
 print(p.name,digest,meta.get('general.architecture'),flush=True)
out=Path('data/test-results');out.mkdir(parents=True,exist_ok=True);(out/'llama-model-inventory.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
