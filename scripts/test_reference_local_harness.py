import os,sys,json,logging
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];home=ROOT/'data/test-results/local-harness-home';home.mkdir(parents=True,exist_ok=True)
os.environ['HERMES_HOME']=str(home);os.environ['TERMINAL_CWD']=str(home);os.environ['OLLAMA_API_KEY']='local-ollama'
sys.path.insert(0,str(ROOT/'indra/SIH-26/hermes-agent'))
from run_agent import AIAgent
state=json.loads((ROOT/'data/cpp-runtime.json').read_text(encoding='utf-8-sig'))
fixture=home/'fixture.txt';fixture.write_text('Local verification code: ORIGO_GGUF_7421',encoding='utf-8')
rows=[]
for label,tools,prompt in [('chat',[],'Reply exactly ORIGO_LOCAL_AGENT_OK. Do not call tools.'),('file_tool',['file'],f'Read {fixture.as_posix()} with read_file. Reply with the exact verification code inside. Do not modify files.')]:
 agent=AIAgent(model=state['alias'],provider='custom',base_url=state['origin']+'/v1',api_key='local-ollama',enabled_toolsets=tools,max_iterations=5,max_tokens=512,quiet_mode=True,skip_context_files=True,skip_memory=True,skip_background_review=True,run_budget_seconds=120,reasoning_config={'enabled':False})
 result=agent.run_conversation(prompt);answer=str(result.get('final_response',''));used=[m.get('tool_call_id') for m in result.get('messages',[]) if m.get('role')=='tool']
 expected='ORIGO_LOCAL_AGENT_OK' if label=='chat' else 'ORIGO_GGUF_7421'
 row={'feature':label,'pass':expected in answer and (label=='chat' or bool(used)),'answer':answer[:200],'tools_used':used,'completed':result.get('completed')};rows.append(row);print(json.dumps(row),flush=True)
logging.shutdown();(ROOT/'data/test-results/reference-local-harness.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
raise SystemExit(0 if all(r['pass'] for r in rows) else 1)
