import httpx,json,time
from pathlib import Path
rows=[]
with httpx.Client(timeout=180) as c:
 for model,expected in [('origo-qwen35:latest','ORIGO_QWEN_OK')]:
  info=c.post('http://127.0.0.1:11434/api/show',json={'model':model});print('capabilities',info.json().get('capabilities'),flush=True)
  start=time.monotonic();r=c.post('http://127.0.0.1:11434/api/chat',json={'model':model,'messages':[{'role':'user','content':'Reply exactly '+expected+'.'}],'stream':False,'think':False,'options':{'num_ctx':4096,'num_predict':128,'temperature':0},'keep_alive':'5m'})
  p=r.json();row={'model':model,'http_status':r.status_code,'seconds':round(time.monotonic()-start,2),'response':p.get('message',{}).get('content'), 'error':p.get('error'),'pass':expected in p.get('message',{}).get('content',''),'eval_count':p.get('eval_count'),'eval_duration':p.get('eval_duration')};rows.append(row);print(json.dumps(row),flush=True)
Path('data/test-results/reference-local-models.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
