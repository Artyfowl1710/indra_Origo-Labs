"""Verify the actual dictation endpoint with offline-generated speech, no mic."""
import base64,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/"indra/SIH-26/hermes-agent")]
os.environ["HERMES_HOME"]=str(ROOT/"data/indra-auto-home")
from hermes_cli.config import load_env
load_env()
from starlette.testclient import TestClient
from hermes_cli.web_server import app,_SESSION_HEADER_NAME,_SESSION_TOKEN
client=TestClient(app);client.headers[_SESSION_HEADER_NAME]=_SESSION_TOKEN
raw=(ROOT/"data/test-results/live-voice-input.wav").read_bytes()
response=client.post("/api/indra/voice/transcribe",json={"data_url":"data:audio/wav;base64,"+base64.b64encode(raw).decode(),"mime_type":"audio/wav"})
body=response.json();text=body.get("transcript","")
report={"case":"Google dictation endpoint with synthetic speech","passed":response.status_code==200 and "service interval" in text.lower(),"status":response.status_code,"provider":body.get("provider"),"transcript":text[:300]}
(ROOT/"data/test-results/google-voice-dictation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report),flush=True)
raise SystemExit(0 if report["passed"] else 1)
