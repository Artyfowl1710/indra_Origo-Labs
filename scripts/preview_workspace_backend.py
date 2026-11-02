"""Isolated acceptance backend; no cloud keys, no model launch and no active-profile writes."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import httpx
import yaml
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/"indra/SIH-26/hermes-agent"
def main():
    output=ROOT/"data/test-results"; home=output/"workspace-acceptance-home";home.mkdir(parents=True,exist_ok=True)
    active=ROOT/"data/indra-auto-home"
    original=yaml.safe_load((active/"config.yaml").read_text(encoding="utf-8"))
    local=dict(original["providers"]["origo-local"])
    local["models"]={
        "origo-auto":{"display_name":"Indra Auto · Qwen coding + OCR","input_modalities":["text","image"],"output_modalities":["text"],"supports_vision":True},
        "origo-qwen35":{"display_name":"Qwen3.5 4B · Coding agent","input_modalities":["text"],"output_modalities":["text"]},
        "origo-vision":{"display_name":"Qwen2-VL OCR 2B · Image reader","input_modalities":["text","image"],"output_modalities":["text"],"supports_vision":True,"tools":False}}
    cfg={"model":{"provider":"custom:origo-local","default":"origo-auto","base_url":local["base_url"],"key_env":"ORIGO_LOCAL_INFERENCE_KEY"},
         "providers":{"origo-local":local},"terminal":{"backend":"local","cwd":str(ROOT/"workspace")},"agent":{"image_input_mode":"auto"}}
    (home/"config.yaml").write_text(yaml.safe_dump(cfg),encoding="utf-8")
    token=dotenv_values(active/".env").get("ORIGO_LOCAL_INFERENCE_KEY","")
    (home/".env").write_text("ORIGO_LOCAL_INFERENCE_KEY="+token+"\n",encoding="utf-8")
    (home/"cache").mkdir(exist_ok=True)
    for name in ("openrouter-live-models.json","openrouter_model_metadata.json"):
        if (active/"cache"/name).exists():shutil.copyfile(active/"cache"/name,home/"cache"/name)
    with socket.socket() as sock:sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
    env={k:v for k,v in os.environ.items() if not k.endswith(("_API_KEY","_TOKEN"))}
    env.update(HERMES_HOME=str(home),HERMES_DESKTOP="1",PYTHONUTF8="1")
    stop=output/"stop-workspace-preview";stop.unlink(missing_ok=True)
    with (output/"workspace-preview-backend.log").open("w",encoding="utf-8") as log:
        child=subprocess.Popen([sys.executable,"-m","hermes_cli.main","dashboard","--no-open","--skip-build","--host","127.0.0.1","--port",str(port)],cwd=CORE,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        try:
            origin=f"http://127.0.0.1:{port}"
            for _ in range(120):
                if child.poll() is not None:raise RuntimeError("Acceptance backend exited")
                try:
                    if httpx.get(origin+"/overview",timeout=1,trust_env=False).status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.5)
            else:raise RuntimeError("Acceptance backend startup timed out")
            (output/"workspace-preview-origin.json").write_text(json.dumps({"origin":origin,"pid":child.pid}),encoding="utf-8")
            print(json.dumps({"origin":origin,"ready":True}),flush=True)
            while not stop.exists() and child.poll() is None:time.sleep(.5)
        finally:
            if child.poll() is None:child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)

if __name__=="__main__":main()
