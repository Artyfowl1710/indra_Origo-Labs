"""Bridge to the installed Indra product's optional workspace services."""
from pathlib import Path
import sys

def workspace(home=None):
    from hermes_constants import get_hermes_home
    root=Path(__file__).resolve().parents[4]
    if str(root) not in sys.path and (root / "origo_runtime/workspace.py").is_file(): sys.path.insert(0,str(root))
    from origo_runtime.workspace import service
    return service(home or get_hermes_home())

def record_event(event, sid, payload, session=None):
    if event not in {"session.info","message.complete","tool.start","tool.complete","approval.request","approval.respond","error","session.model_changed"}: return
    import hashlib
    import json
    import logging
    session=session or {}; agent=session.get("agent")
    record={"session":sid,"provider":getattr(agent,"provider",None),"model":getattr(agent,"model",None),
            "payload_hash":hashlib.sha256(json.dumps(payload or {},sort_keys=True,default=str).encode()).hexdigest()}
    if isinstance(payload,dict):
        for key in ("tool_name","tool","duration_ms","input_tokens","output_tokens","model","provider","status"):
            value=payload.get(key)
            if isinstance(value,(str,int,float,bool)) and len(str(value))<240: record[key]=value
    try:
        current=workspace(session.get("profile_home"));current.audit.append(event, record)
        chat=session.get("session_key") or getattr(agent,"session_id",None)
        if chat and event in {"tool.start","tool.complete","approval.request","approval.respond","error","session.model_changed"}:
            from origo_runtime.conversation_records import ConversationRecords
            import uuid
            label=str(record.get("tool_name") or record.get("tool") or "")
            if not label and isinstance(payload,dict):label=str(payload.get("name") or "")[:160]
            summary=event+(": "+label if label else "")
            if isinstance(payload,dict):
                status=payload.get("status") or (payload.get("choice") if event=="approval.respond" else None)
                if isinstance(status,str):summary+=" · "+status[:120]
                args=payload.get("args") or payload.get("arguments")
                if isinstance(args,str) and len(args)<16000:
                    try:args=json.loads(args)
                    except ValueError:args={}
                if isinstance(args,dict):
                    details={key:str(args[key])[:800] for key in ("command","path","file_path","url","query","description") if isinstance(args.get(key),(str,int,float))}
                    if details:
                        from app.rag import _redact
                        excerpt,_=_redact(json.dumps(details,ensure_ascii=False))
                        summary+="\nRequested: "+excerpt
            ConversationRecords(current.root).save(str(chat),[{"id":uuid.uuid4().hex,"kind":"action","role":"note","text":summary,"model":record.get("model"),"provider":record.get("provider")}],source="runtime")
    except Exception as error:
        logging.getLogger(__name__).error("Provenance write failed (%s)",type(error).__name__)

def record_auxiliary_route(provider,model):
    import logging
    try: workspace().audit.append("inference.route_selected",{"provider":provider or "auto","model":model or "default","task":"auxiliary"})
    except Exception as error: logging.getLogger(__name__).error("Provenance write failed (%s)",type(error).__name__)
