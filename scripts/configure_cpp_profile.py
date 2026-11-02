from pathlib import Path
import os,yaml,shutil,sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
profile=os.environ.get('ORIGO_CPP_PROFILE','indra-cpp-home')
if profile not in {'indra-cpp-home','indra-auto-home'}:raise ValueError('Unknown local product profile')
home=Path(os.environ.get('ORIGO_HOME') or root/'data'/profile).resolve()
home.mkdir(parents=True,exist_ok=True)
p=home/'config.yaml'
existing_profile=p.exists()
source=p if p.exists() else root/'data/indra-local-home/config.yaml'
cfg=yaml.safe_load(source.read_text(encoding='utf-8'))
model=os.environ['ORIGO_CPP_ALIAS'];url=os.environ['ORIGO_CPP_ORIGIN']+'/v1'
key_env='ORIGO_LOCAL_INFERENCE_KEY' if profile=='indra-auto-home' else 'OPENAI_API_KEY'
old_model=cfg.get('model',{})
use_local=(not existing_profile or profile!='indra-auto-home' or
           isinstance(old_model,dict) and (old_model.get('provider') in {'custom:origo-local','origo-local'} or
           old_model.get('provider')=='custom' and old_model.get('default')=='origo-auto'))
if use_local:
 cfg['model']={'default':model,'provider':'custom','base_url':url,'key_env':key_env,'max_tokens':2048,'context_length':int(os.environ.get('ORIGO_CPP_CONTEXT','16384'))}
elif isinstance(old_model,dict) and old_model.get('key_env')=='ORIGO_LOCAL_INFERENCE_KEY':
 # Heal endpoint metadata left by the older cross-provider model switch.
 old_model.pop('key_env',None)
 old_model.pop('supports_vision',None)
if profile=='indra-auto-home':
 if use_local:
  cfg['model']['provider']='custom:origo-local'
  cfg['model']['supports_vision']=True
 cfg.setdefault('agent',{}).setdefault('image_input_mode','auto')
 cfg.setdefault('providers',{})['origo-local']={'name':'On this PC · Qwen','base_url':url,'key_env':key_env,'default_model':model,'api_mode':'chat_completions',
  'models': {
   'origo-auto': {'display_name':'Indra Auto · Qwen coding + Qwen2-VL OCR','input_modalities':['text','image'],'output_modalities':['text'],'supports_vision':True},
   'origo-qwen35': {'display_name':'Qwen3.5 4B · Coding agent','input_modalities':['text'],'output_modalities':['text'],'supports_vision':False},
   'origo-vision': {'display_name':'Qwen2-VL OCR 2B · Image reader','input_modalities':['text','image'],'output_modalities':['text'],'supports_vision':True,'tools':False}}}
 # Profile-scoped credentials must be available to the gateway's isolated
 # secret loader. This is a newly generated loopback token, never a cloud key.
 from dotenv import set_key
 token=os.environ.get(key_env,'')
 if len(token)<32:raise ValueError('The local routing credential is missing')
 set_key(str(home/'.env'),key_env,token,quote_mode='always')
if use_local:cfg['fallback_model']=None
cfg.setdefault('security',{}).setdefault('untrusted_content_guard',True)
for row in cfg.get('auxiliary',{}).values():
 if isinstance(row,dict) and (profile!='indra-auto-home' or row.get('provider') in {'custom','custom:origo-local','origo-local'} and row.get('model') in {'origo-auto','origo-qwen35','origo-vision'}):
  row.update({'provider':'custom','base_url':url,'model':row.get('model',model) if profile=='indra-auto-home' else model,'key_env':key_env})
from origo_runtime.phone_config import apply_settings
cfg=apply_settings(home,cfg)
p.write_text(yaml.safe_dump(cfg,sort_keys=False,allow_unicode=True),encoding='utf-8')
for name in ['skills','skins','dashboard-themes']:
 if not (home/name).exists():shutil.copytree(root/'indra/SIH-26'/name,home/name)
