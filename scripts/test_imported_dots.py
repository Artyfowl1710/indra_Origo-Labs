import getpass, os, sys, tempfile, json, logging
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='origo-dots-') as folder:
 os.environ['HERMES_HOME']=folder
 os.environ['TERMINAL_CWD']=folder
 os.environ['OPENROUTER_API_KEY']=getpass.getpass('Temporary OpenRouter key: ')
 sys.path.insert(0,str(ROOT/'indra/SIH-26/hermes-agent'))
 from run_agent import AIAgent
 results=[]
 for label,toolsets,prompt in [
  ('text',[], 'Reply exactly ORIGO_DOTS_OK. Do not call tools.'),
  ('file_read',['file'],f'Read the file {folder}/fixture.txt using read_file. Reply with its exact verification phrase. Do not write or modify any file.')]:
  Path(folder,'fixture.txt').write_text('Verification phrase: ORIGO_FIXTURE_7421',encoding='utf-8')
  agent=AIAgent(model='dots-studio/dots-3-note-preview:free',provider='openrouter',api_key=os.environ['OPENROUTER_API_KEY'],base_url='https://openrouter.ai/api/v1',enabled_toolsets=toolsets,max_iterations=4,max_tokens=256,quiet_mode=True,skip_context_files=True,skip_memory=True,skip_background_review=True,run_budget_seconds=90)
  result=agent.run_conversation(prompt)
  answer=str(result.get('final_response',result.get('response',result.get('answer',''))))
  expected='ORIGO_DOTS_OK' if label=='text' else 'ORIGO_FIXTURE_7421'
  row={'tools_used': [m.get('name') or m.get('tool_call_id') for m in result.get('messages',[]) if m.get('role')=='tool'], 'feature':label,'pass':expected in answer,'response':answer[:160],'result_keys':list(result)}
  results.append(row);print(json.dumps(row))
 logging.shutdown()
 os.environ.pop('OPENROUTER_API_KEY',None)
 out=ROOT/'data'/'test-results';out.mkdir(parents=True,exist_ok=True);(out/'dots-live.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
