import asyncio, getpass, os, sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
async def main():
    with tempfile.TemporaryDirectory(prefix='origo-harness-') as folder:
        os.environ['INDRA_DATA_DIR']=folder
        os.environ['INDRA_WORKSPACE']=folder
        from app.agent import Agent
        from app.store import Store
        from app.providers import OpenAICompatibleProvider
        provider=OpenAICompatibleProvider()
        if sys.argv[1]=='openrouter':
            os.environ['INDRA_HOSTED_BASE_URL']='https://openrouter.ai/api/v1'
            os.environ['INDRA_HOSTED_API_KEY']=getpass.getpass('Temporary key: ')
            os.environ['INDRA_HOSTED_MODEL']='dots-studio/dots-3-note-preview:free'
            provider.use_profile('hosted');os.environ.pop('INDRA_HOSTED_API_KEY',None)
        else:
            os.environ['OPENAI_BASE_URL']='http://127.0.0.1:11434/v1'
            os.environ['MODEL']='qwen2.5:1.5b'
            provider.use_profile('local')
        try:
            result=await Agent(provider,Store()).run('Reply exactly ORIGO_OK. Do not call tools.',mode='plan',allowed_tool_names=[],duration_cap_seconds=90)
            print('MODEL',result.get('model'),'STATUS',result.get('status'),'ANSWER',str(result.get('answer'))[:200])
            return 0 if 'ORIGO_OK' in str(result.get('answer')) else 1
        finally:await provider.aclose()
if __name__=='__main__':raise SystemExit(asyncio.run(main()))
