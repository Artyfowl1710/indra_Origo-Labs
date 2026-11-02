"""Configured OpenAI-compatible reasoning models used with the speech pipeline."""
import os,ipaddress
from urllib.parse import urlsplit
from dotenv import dotenv_values
from hermes_cli.config import load_config
from hermes_constants import get_hermes_home

def connections():
    rows=[];providers=load_config().get("providers",{})
    for key,entry in (providers.items() if isinstance(providers,dict) else []):
        if not isinstance(entry,dict) or entry.get("voice_enabled") is not True:continue
        models=entry.get("models",{})
        names=list(models) if isinstance(models,(dict,list)) else []
        default=entry.get("default_model") or entry.get("model")
        if default and default not in names:names.insert(0,default)
        for model in names:
            if not isinstance(model,str) or not model:continue
            rows.append({"id":f"custom:{key}:{model}","provider":f"custom:{key}","model":model,"label":model,"transport":"chat-speech","configured":bool(entry.get("base_url")),"output":"text + device speech"})
    return rows

def resolve(provider,model):
    key=provider.removeprefix("custom:");entry=load_config().get("providers",{}).get(key)
    if not isinstance(entry,dict) or entry.get("voice_enabled") is not True:raise ValueError("Voice connection is not enabled")
    if not any(row["provider"]==provider and row["model"]==model for row in connections()):raise ValueError("Select a configured voice model")
    base=str(entry.get("base_url") or "").rstrip("/");url=urlsplit(base)
    if url.scheme not in {"http","https"} or not url.hostname or url.username or url.password or url.query or url.fragment:raise ValueError("Invalid voice endpoint")
    env=dotenv_values(get_hermes_home()/".env");name=entry.get("key_env") or entry.get("api_key_env") or ""
    secret=str(env.get(name) or os.environ.get(name) or entry.get("api_key") or "")
    try:local=ipaddress.ip_address(url.hostname).is_loopback
    except ValueError:local=url.hostname=="localhost"
    if secret and url.scheme!="https" and not local:raise ValueError("Remote voice credentials require HTTPS")
    return base,secret

async def native_transcription(provider,model,data_url,client):
    """Muse Spark audio input uses audio_url; do not assume other hosts share it."""
    base,key=resolve(provider,model)
    if urlsplit(base).hostname!="inference.baseten.co":return None
    entry=load_config().get("providers",{}).get(provider.removeprefix("custom:"),{})
    metadata=entry.get("models",{}).get(model,{}) if isinstance(entry.get("models"),dict) else {}
    if "audio" not in metadata.get("input_modalities",entry.get("input_modalities",[])):return None
    from agent.model_request_policy import enforce_model_request
    enforce_model_request({"audio":data_url,"model":model,"endpoint":base},task="voice-transcription")
    response=await client.post(base+"/chat/completions",headers={"Authorization":"Bearer "+key},json={"model":model,"messages":[{"role":"user","content":[{"type":"text","text":"Transcribe only the speech in this audio, preserving its language. Return only the words spoken. If it is silent, return an empty response."},{"type":"audio_url","audio_url":{"url":data_url}}]}],"max_tokens":2048})
    if response.status_code>=300:raise ValueError("Selected audio model rejected transcription. Check its key and quota.")
    text=response.json()["choices"][0]["message"]["content"]
    if not isinstance(text,str):raise ValueError("Selected audio model did not return a transcription")
    return {"ok":True,"transcript":text[:10000].strip(),"provider":provider,"model":model}
