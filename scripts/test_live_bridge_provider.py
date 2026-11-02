"""Real Live provider through the authenticated local bridge; synthetic speech only."""
import argparse
import asyncio
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from urllib.parse import urlencode
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/"indra/SIH-26/hermes-agent")]
os.environ["HERMES_HOME"]=str(ROOT/"data/indra-auto-home")


async def run(model):
    from hermes_cli.config import load_env
    load_env()
    from starlette.testclient import TestClient
    from hermes_cli.web_server import app,_SESSION_HEADER_NAME,_SESSION_TOKEN
    from origo_runtime.workspace import Workspace
    from hermes_cli.origo_workspace import workspace
    import numpy as np
    report={"model":model,"transport":"local-bridge","synthetic_speech":True,"passed":False}
    started=time.monotonic(); audio=0; transcript=""; tool=False; ready=False; session=None
    output=ROOT/"data/test-results"
    try:
        with tempfile.TemporaryDirectory(dir=output,prefix="voice-bridge-rag-") as folder, TestClient(app,base_url="http://127.0.0.1") as client:
            client.headers[_SESSION_HEADER_NAME]=_SESSION_TOKEN
            knowledge=Workspace(Path(folder));knowledge.engine().ingest_bytes("voice-fixture.md","text/plain",b"The service interval is six months.")
            url="ws://127.0.0.1/api/indra/voice/live?"+urlencode({"token":_SESSION_TOKEN,"model":model})
            with client.websocket_connect(url) as socket:
                setup={"model":"models/"+model,"generationConfig":{"responseModalities":["AUDIO"]},
                    "outputAudioTranscription":{},"inputAudioTranscription":{},"sessionResumption":{},
                    "contextWindowCompression":{"slidingWindow":{}},"systemInstruction":{"parts":[{"text":"You are Indra by Origo Labs. When asked about the service interval, call search_knowledge before answering. Reply in English with only the retrieved interval."}]},
                    "tools":[{"functionDeclarations":[{"name":"search_knowledge","description":"Search the user's service documentation.","behavior":"NON_BLOCKING","parameters":{"type":"OBJECT","properties":{"query":{"type":"STRING"}},"required":["query"]}}]}]}
                if "extended-thinking" in model:setup["generationConfig"]["thinkingConfig"]={"thinkingLevel":"MEDIUM"}
                if model.startswith("gemini-2.5-"):setup["generationConfig"]["thinkingConfig"]={"thinkingBudget":-1}
                await asyncio.to_thread(socket.send_json,{"setup":setup})
                deadline=time.monotonic()+65
                while time.monotonic()<deadline:
                    message=await asyncio.wait_for(asyncio.to_thread(socket.receive_json),timeout=min(25,max(.1,deadline-time.monotonic())))
                    if message.get("error"):
                        report["error_code"]=message["error"].get("code");break
                    if message.get("indraSession"):session=message["indraSession"].get("id")
                    if "setupComplete" in message and not ready:
                        ready=True
                        with wave.open(str(output/"live-voice-input.wav"),"rb") as wav:
                            assert wav.getsampwidth()==2
                            values=np.frombuffer(wav.readframes(wav.getnframes()),dtype="<i2").reshape(-1,wav.getnchannels()).mean(axis=1)
                            samples=np.interp(np.arange(int(len(values)*16000/wav.getframerate()))*wav.getframerate()/16000,np.arange(len(values)),values).astype("<i2").tobytes()
                        for offset in range(0,len(samples),4096):
                            await asyncio.to_thread(socket.send_json,{"realtimeInput":{"audio":{"mimeType":"audio/pcm;rate=16000","data":base64.b64encode(samples[offset:offset+4096]).decode()}}})
                            await asyncio.sleep(.128)
                        await asyncio.to_thread(socket.send_json,{"realtimeInput":{"audioStreamEnd":True}})
                    for call in message.get("toolCall",{}).get("functionCalls",[]):
                        if call.get("name")=="search_knowledge":
                            result=await asyncio.to_thread(knowledge.context,call.get("args",{}).get("query","service interval"))
                            tool=bool(result["citations"])
                            scheduling={} if "extended-thinking" in model or model.startswith("gemini-3.1-") else {"scheduling":"INTERRUPT"}
                            await asyncio.to_thread(socket.send_json,{"toolResponse":{"functionResponses":[{"id":call["id"],"name":call["name"],"response":{"result":result},**scheduling}]}})
                    content=message.get("serverContent",{})
                    transcript+=content.get("outputTranscription",{}).get("text","")
                    for part in content.get("modelTurn",{}).get("parts",[]):
                        inline=part.get("inlineData",{})
                        if inline.get("mimeType","").startswith("audio/pcm"):audio+=len(base64.b64decode(inline["data"]))
                    if tool and audio and (content.get("turnComplete") or content.get("interactionStatus")=="IDLE"):break
            events=workspace().audit.recent()
            report["signed_audit_started"]=any(e["kind"]=="voice.live_started" and e["payload"].get("session")==session for e in events)
            report["signed_audit_ended"]=any(e["kind"]=="voice.live_ended" and e["payload"].get("session")==session for e in events)
            report["audit_valid"]=workspace().audit.verify()["valid"]
    except Exception as error:
        # Never print exception details: transport exceptions may include credentials.
        report["error_type"]=type(error).__name__
        code=getattr(error,"code",None)
        if code:report["close_code"]=code
    report.update(setup=ready,rag_tool_used=tool,audio_bytes=audio,transcript=transcript[:300],seconds=round(time.monotonic()-started,2))
    correct="six month" in transcript.lower() or "6 month" in transcript.lower()
    report["passed"]=bool(session and ready and tool and audio and correct and report.get("signed_audit_started") and report.get("signed_audit_ended") and report.get("audit_valid"))
    return report


if __name__=="__main__":
    from hermes_cli.web_routers.indra_voice import MODELS
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model",choices=MODELS,default=MODELS[0])
    parser.add_argument("--output",type=Path,default=ROOT/"data/test-results/live-bridge-provider-acceptance.json")
    args=parser.parse_args()
    report=asyncio.run(run(args.model))
    args.output.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report),flush=True)
    raise SystemExit(0 if report["passed"] else 1)
