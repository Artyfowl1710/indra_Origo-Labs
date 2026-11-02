from pathlib import Path
import sys,hashlib,json
sys.path.insert(0,str(Path('.builddeps').resolve()))
import pefile
root=Path(r'C:\Users\khatr\OneDrive\Desktop\SIH-26-main\SIH-26\hermes-agent\backend\bin')
rows=[]
for name in ['llama-server.exe','llama-server-impl.dll','llama.dll','ggml-cuda.dll','cudart64_12.dll','cudart64_13.dll','cublas64_12.dll','cublas64_13.dll','cublasLt64_12.dll','cublasLt64_13.dll','llama-swap.exe']:
 p=root/name
 with p.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
 pe=pefile.PE(str(p),fast_load=True);pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
 imports=[row.dll.decode(errors='replace') for row in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[])]
 rows.append({'file':name,'sha256':digest,'machine':hex(pe.FILE_HEADER.Machine),'imports':imports})
 print(name, digest[:16],','.join(x for x in imports if any(t in x.lower() for t in ['llama','cuda','cublas','ggml'])))
 pe.close()
Path('data/test-results/llama-binary-inventory.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
