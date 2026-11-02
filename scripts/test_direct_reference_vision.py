from pathlib import Path
import os,subprocess,socket,time,json,httpx
root=Path.cwd();runtime=Path(os.environ['LOCALAPPDATA'])/'Programs/Ollama/lib/ollama';models=Path(r'C:\Users\khatr\OneDrive\Desktop\SIH-26-main\SIH-26\hermes-agent\backend\models')
env=os.environ.copy();env['GGML_BACKEND_PATH']=str(runtime/'cuda_v13/ggml-cuda.dll');env['PATH']=str(runtime/'cuda_v13')+os.pathsep+env['PATH']
from PIL import Image,ImageDraw,ImageFont
import io,base64
im=Image.new('RGB',(280,120),'white');draw=ImageDraw.Draw(im);draw.text((20,30),'INDRA42',fill='black',font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',48));buf=io.BytesIO();im.save(buf,format='PNG');image_url='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
rows=[]
for alias,filename,expected in [('origo-vision','Qwen2-VL-OCR-2B-Instruct.Q4_K_M.gguf','INDRA42')]:
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 logpath=root/'logs'/f'{alias}-direct.log';logpath.parent.mkdir(exist_ok=True)
 with logpath.open('wb') as log:
  args=[str(runtime/'llama-server.exe'),'--model',str(models/filename),'--alias',alias,'--host','127.0.0.1','--port',str(port),'--n-gpu-layers','99','--ctx-size','4096','--batch-size','128','--ubatch-size','64','--parallel','1','--threads','8','--no-warmup','--jinja','--reasoning','off']
  args += ['--mmproj',str(models/'mmproj-Qwen2-VL-2B-Instruct-f16.gguf')]
  process=subprocess.Popen(args,env=env,cwd=root,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
  try:
   with httpx.Client(timeout=90) as c:
    ready=False
    for i in range(100):
     if process.poll() is not None:raise RuntimeError('runtime exited: '+str(process.returncode))
     try:
      r=c.get(f'http://127.0.0.1:{port}/health',timeout=1)
      if r.status_code==200:ready=True;break
     except httpx.HTTPError:pass
     time.sleep(.5)
    if not ready:raise RuntimeError('startup timeout')
    print(alias,'ready',flush=True);start=time.monotonic();r=c.post(f'http://127.0.0.1:{port}/v1/chat/completions',json={'model':alias,'messages':[{'role':'user','content':[{'type':'text','text':'Read the code in the image. Reply only with that code.'},{'type':'image_url','image_url':{'url':image_url}}]}],'max_tokens':96,'temperature':0,'chat_template_kwargs':{'enable_thinking':False}})
    p=r.json();answer=p.get('choices',[{}])[0].get('message',{}).get('content','');row={'model':alias,'http':r.status_code,'pass':expected in str(answer),'answer':answer,'seconds':round(time.monotonic()-start,2)};rows.append(row);print(json.dumps(row),flush=True)
  except Exception as e:row={'model':alias,'pass':False,'error':str(e)};rows.append(row);print(json.dumps(row),flush=True)
  finally:
   process.terminate()
   try:process.wait(timeout=10)
   except subprocess.TimeoutExpired:process.kill();process.wait()
Path('data/test-results/direct-llamacpp-vision.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
