"""Real local-agent acceptance using only synthetic knowledge and identity."""
import json
import asyncio
import argparse
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.parse import urlsplit
import yaml
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/"indra/SIH-26/hermes-agent")]

def main(base=None,key=None,freshness=False):
    if base is None:
        active=ROOT/"data/indra-auto-home"
        config=yaml.safe_load((active/"config.yaml").read_text(encoding="utf-8"))
        base=config["providers"]["origo-local"]["base_url"]
        key=dotenv_values(active/".env").get("ORIGO_LOCAL_INFERENCE_KEY")
    url=urlsplit(base)
    if url.scheme!="http" or url.hostname!="127.0.0.1" or url.path!="/v1":raise ValueError("Expected local inference gateway")
    if not key:raise ValueError("No local gateway credential")
    output=ROOT/"data/test-results"
    with tempfile.TemporaryDirectory(prefix="workspace-live-",dir=output,ignore_cleanup_errors=True) as folder:
        home=Path(folder);os.environ["HERMES_HOME"]=str(home)
        cfg={"model":{"provider":"custom","default":"origo-qwen35","base_url":base,"context_length":16384,"supports_vision":False},
             "terminal":{"backend":"local","cwd":str(home)},"agent":{"image_input_mode":"auto"}}
        (home/"config.yaml").write_text(yaml.safe_dump(cfg),encoding="utf-8")
        from origo_runtime.workspace import Workspace
        knowledge=Workspace(home)
        knowledge.save_identity({"name":"Asha","interests":"Robotics","instructions":"Use source citations when answering from my documents.","use_in_requests":True,"setup_complete":True})
        review=knowledge.preview_memory_import(b"My preferred project language is Python.")
        knowledge.commit_memory_import(review["id"],["0"],review["revision"])
        knowledge.engine().ingest_bytes("maintenance.md","text/plain",b"The vehicles require routine maintenance every six months. Inspect tires and brakes during each service.")
        if freshness:
            engine=knowledge.engine()
            old=engine.list_documents()[0]
            new=engine.ingest_bytes("maintenance_current.md","text/plain",b"Document: Vehicle service\nVersion: 2\nOwner: Fleet team\nReview due: 2020-01-01\nThe vehicles require routine maintenance every twelve months. Inspect tires and brakes during each service.")
            value=next(doc for doc in engine.list_documents() if doc["doc_id"]==new["doc_id"])["governance"]
            knowledge.review_document("library",new["doc_id"],{**value,"status":"current"},value["revision"])
            value=old["governance"]
            knowledge.review_document("library",old["doc_id"],{**value,"family":"Vehicle service","status":"superseded","superseded_by":new["doc_id"]},value["revision"])
        question="What is my preferred name, which programming language do I prefer for projects, and how often should the vehicles receive routine maintenance?"
        if freshness:question+=" Also warn me if the source is overdue for review."
        evidence=knowledge.context(question)
        from run_agent import AIAgent
        started=time.perf_counter();agent=None
        try:
            agent=AIAgent(provider="custom",model="origo-qwen35",base_url=base,api_key=key,max_iterations=2,max_tokens=256,
                          reasoning_config={"enabled":False},enabled_toolsets=[],skip_context_files=True,skip_memory=True,
                          skip_background_review=True,quiet_mode=True)
            result=agent.run_conversation(question+"\n\n"+evidence["context"])
            answer=str(result.get("final_response",""))
            interval=r"\b(?:twelve|12)\s+months?\b" if freshness else r"\b(?:six|6)\s+months?\b"
            passed="asha" in answer.lower() and "python" in answer.lower() and bool(re.search(interval,answer,re.I)) and "[R1]" in answer
            if freshness:passed=passed and "overdue" in answer.lower() and not re.search(r"\b(?:six|6)\s+months?\b",answer,re.I)
            report={"case":"local-qwen-offline-rag-personal-memory","passed":passed,"model":"origo-qwen35",
                    "retrieval":evidence["mode"],"citations":len(evidence["citations"]),"reviewed_facts":len(knowledge.identity()["facts"]),"seconds":round(time.perf_counter()-started,2),"answer":answer[:500]}
        except Exception as error:
            report={"case":"local-qwen-offline-rag-personal-memory","passed":False,"error_type":type(error).__name__}
        finally:
            if agent:agent.close()
        (output/("knowledge-freshness-agent-live.json" if freshness else "workspace-agent-live.json")).write_text(json.dumps(report,indent=2),encoding="utf-8");print(json.dumps(report),flush=True)
        return report["passed"]

async def isolated(freshness=False):
    from origo_runtime.llamacpp import LlamaRuntime
    runtime=LlamaRuntime(Path(os.environ["LOCALAPPDATA"])/"Programs/Ollama/lib/ollama",
                        Path(r"C:\Users\khatr\OneDrive\Desktop\SIH-26-main\SIH-26\hermes-agent\backend\models"),
                        ROOT/"data/test-results/memory-model-runtime", "auto")
    try:
        origin=await runtime.ensure("text")
        return main(origin+"/v1","isolated-local-fixture",freshness)
    finally:
        await runtime.stop()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--isolated",action="store_true",help="Use an owned signed local model process rather than the user's gateway")
    parser.add_argument("--freshness",action="store_true",help="Verify superseded-source exclusion and overdue warnings with the actual model")
    args=parser.parse_args()
    raise SystemExit(0 if (asyncio.run(isolated(args.freshness)) if args.isolated else main(freshness=args.freshness)) else 1)
