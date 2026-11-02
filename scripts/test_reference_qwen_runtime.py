import httpx,json,time
from pathlib import Path
base='http://127.0.0.1:11434'
with httpx.Client(timeout=180) as client:
 show=client.post(base+'/api/show',json={'model':'qwen3.5-4b:latest'});show.raise_for_status();data=show.json();print('capabilities',data.get('capabilities'),'template_chars',len(data.get('template','')),flush=True)
 start=time.monotonic();response=client.post(base+'/api/chat',json={'model':'qwen3.5-4b:latest','messages':[{'role':'user','content':'Reply exactly ORIGO_LOCAL_OK.'}],'think':False,'stream':False,'options':{'num_ctx':4096,'num_predict':64,'temperature':0},'keep_alive':'5m'})
 print('http',response.status_code,'elapsed_seconds',round(time.monotonic()-start,2),flush=True)
 payload=response.json();print(json.dumps(payload)[:1600],flush=True)
 out=Path('data/test-results');out.mkdir(parents=True,exist_ok=True);(out/'reference-qwen-local-runtime.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
