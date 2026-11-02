from pathlib import Path
import os,sys,json,time,logging,httpx
root=Path.cwd();state=json.loads((root/'data/cpp-runtime.json').read_text(encoding='utf-8-sig'))
httpx.get(state['origin']+'/health',timeout=3).raise_for_status()
os.environ['HERMES_HOME']=str(root/'data/indra-cpp-home');os.environ['ORIGO_SOCIAL_TOOL_POLICY']='1';sys.path.insert(0,str(root/'indra/SIH-26/hermes-agent'))
from run_agent import AIAgent
agent=AIAgent(model=state['alias'],provider='custom',base_url=state['origin']+'/v1',api_key='local-llamacpp',max_iterations=3,max_tokens=128,quiet_mode=True,skip_context_files=True,skip_memory=True,skip_background_review=True,run_budget_seconds=120)
start=time.monotonic();result=agent.run_conversation('hi');calls=[m for m in result.get('messages',[]) if m.get('role')=='tool'];row={'prompt':'hi','completed':result.get('completed'),'tool_calls':len(calls),'response':str(result.get('final_response',''))[:300],'seconds':round(time.monotonic()-start,2)}
print(json.dumps(row),flush=True);(root/'data/test-results/social-turn-live.json').write_text(json.dumps(row,indent=2),encoding='utf-8');fixture=root/'data/test-results/social-followup.txt';fixture.write_text('ORIGO_FOLLOWUP_7421',encoding='utf-8')
followup=agent.run_conversation('Read '+fixture.as_posix()+' using read_file and return its verification code. Do not change files.',conversation_history=result.get('messages',[]))
follow_calls=[m for m in followup.get('messages',[]) if m.get('role')=='tool'];follow={'completed':followup.get('completed'),'tool_calls':len(follow_calls),'tool_results':[str(m.get('content',''))[:700] for m in follow_calls],'response':str(followup.get('final_response',''))[:300]};follow['pass']='ORIGO_FOLLOWUP_7421' in follow['response'] and bool(follow_calls)
print(json.dumps(follow),flush=True);(root/'data/test-results/social-followup-live.json').write_text(json.dumps(follow,indent=2),encoding='utf-8');logging.shutdown()
