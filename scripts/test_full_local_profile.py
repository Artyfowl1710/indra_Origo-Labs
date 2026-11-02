import os,sys,json,logging
from pathlib import Path
root=Path.cwd();os.environ['HERMES_HOME']=str(root/'data/indra-cpp-home');os.environ['OPENAI_API_KEY']='local-llamacpp';sys.path.insert(0,str(root/'indra/SIH-26/hermes-agent'))
from run_agent import AIAgent
state=json.loads((root/'data/cpp-runtime.json').read_text(encoding='utf-8-sig'))
agent=AIAgent(model=state['alias'],provider='custom',base_url=state['origin']+'/v1',api_key='local-llamacpp',max_iterations=3,max_tokens=256,quiet_mode=True,skip_context_files=True,skip_memory=True,skip_background_review=True,run_budget_seconds=180,reasoning_config={'enabled':False})
result=agent.run_conversation('Reply exactly ORIGO_FULL_PROFILE_OK. Do not use tools.')
answer=str(result.get('final_response',''));row={'pass':'ORIGO_FULL_PROFILE_OK' in answer,'answer':answer[:200],'completed':result.get('completed'),'input_tokens':result.get('input_tokens'),'context':state['context']};print(json.dumps(row),flush=True)
(root/'data/test-results/local-full-profile.json').write_text(json.dumps(row,indent=2),encoding='utf-8');logging.shutdown()
