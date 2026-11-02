"""Real local Qwen tool-choice acceptance using an owned temporary profile."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/"indra/SIH-26/hermes-agent")]


async def main():
    from origo_runtime.llamacpp import LlamaRuntime
    output=ROOT/"data/test-results";output.mkdir(parents=True,exist_ok=True)
    runtime=LlamaRuntime(Path(os.environ["LOCALAPPDATA"])/"Programs/Ollama/lib/ollama",
        Path(r"C:\Users\khatr\OneDrive\Desktop\SIH-26-main\SIH-26\hermes-agent\backend\models"),output/"chat-title-runtime","auto")
    agent=None;db=None
    try:
        origin=await runtime.ensure("text")
        with tempfile.TemporaryDirectory(prefix="chat-title-live-",dir=output,ignore_cleanup_errors=True) as temporary:
            home=Path(temporary);os.environ["HERMES_HOME"]=str(home)
            config={"model":{"provider":"custom","default":"origo-qwen35","base_url":origin+"/v1","context_length":16384},
                    "auxiliary":{"title_generation":{"enabled":False}},"security":{"untrusted_content_guard":True},
                    "terminal":{"backend":"docker","cwd":"/workspace","docker_image":"indra-documents:1"}}
            (home/"config.yaml").write_text(json.dumps(config),encoding="utf-8")
            from hermes_state import SessionDB
            from run_agent import AIAgent
            from hermes_cli.origo_workspace import workspace
            db=SessionDB(home/"state.db");db.create_session("other",source="cli");db.set_session_title("other","Dockyard Plan")
            agent=AIAgent(provider="custom",model="origo-qwen35",base_url=origin+"/v1",api_key="isolated-local-fixture",
                          max_iterations=3,max_tokens=384,enabled_toolsets=["file"],skip_context_files=True,skip_memory=True,
                          skip_background_review=True,quiet_mode=True,session_id="rename-real-fixture",session_db=db,
                          run_budget_seconds=120,reasoning_config={"enabled":False})
            started=time.perf_counter()
            result=agent.run_conversation("Use rename_current_chat to rename this current chat to Dockyard Plan. Do not write files or use other tools. Then report the exact title returned by the tool; it may add a suffix if the name is taken.")
            title=db.get_session_title("rename-real-fixture")
            used=[call.get("function",{}).get("name") for message in result.get("messages",[]) if isinstance(message,dict) for call in (message.get("tool_calls") or []) if isinstance(call,dict)]
            audit=workspace().audit
            resolved=[event["payload"].get("tool") for event in audit.recent() if event["kind"]=="chat.renamed"]
            passed="rename_current_chat" in resolved and title=="Dockyard Plan #2" and db.get_session_title("other")=="Dockyard Plan" and audit.verify()["valid"]
            report={"passed":passed,"model":"origo-qwen35","title":title,"tools":used,"resolved_tools":resolved,"other_chat_unchanged":db.get_session_title("other")=="Dockyard Plan",
                    "audit_valid":audit.verify()["valid"],"seconds":round(time.perf_counter()-started,2),"answer":str(result.get("final_response",""))[:400],
                    "scope":"Synthetic current-chat metadata fixture with real model/tool/SQLite/Audit paths; no cloud calls or external channel renames."}
            (output/"chat-title-real-model.json").write_text(json.dumps(report,indent=2),encoding="utf-8");print(json.dumps(report),flush=True)
            return passed
    finally:
        if agent:agent.close()
        if db:db.close()
        await runtime.stop()


if __name__=="__main__":raise SystemExit(0 if asyncio.run(main()) else 1)
