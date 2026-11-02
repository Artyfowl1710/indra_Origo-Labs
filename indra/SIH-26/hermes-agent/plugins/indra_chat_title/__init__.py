"""Product-owned current-chat metadata tool; no transcript or prompt changes."""
import hashlib
import json
from pathlib import Path
import uuid

SCHEMA={"name":"rename_current_chat","description":"Give this current chat a concise, useful title as its focus becomes clear or when the user asks. Only the active chat can be renamed. Never place secrets in titles. A user-chosen title needs fresh human approval before replacement. Returns the actual saved title, including a suffix if the name is taken. This only changes local chat metadata, not the transcript, project files or external channel names.",
        "parameters":{"type":"object","properties":{"title":{"type":"string","minLength":1,"maxLength":80}},"required":["title"],"additionalProperties":False}}


def available():
    return (Path(__file__).resolve().parents[5]/"origo_runtime/workspace.py").is_file()


def rename(args, *, session_id=None, **kwargs):
    try:
        if not isinstance(args,dict) or set(args)!={"title"}:
            raise ValueError("Provide only a title; the active chat is selected by the harness")
        if not isinstance(session_id,str) or not session_id or len(session_id)>240:
            raise ValueError("This tool needs the active chat identity from the harness")
        raw=args["title"]
        if not isinstance(raw,str) or not 1<=len(raw)<=80:
            raise ValueError("Choose a title of 1–80 characters")
        from hermes_state import SessionDB
        title=SessionDB.sanitize_title(raw)
        if not title:raise ValueError("Choose a visible, nonempty title")
        from hermes_cli.origo_workspace import workspace
        current_workspace=workspace()
        from app.content_safety import scan_document
        from origo_runtime.personal_memory import SECRET
        if scan_document(title)["quarantined"] or SECRET.search(title):
            raise ValueError("Choose a descriptive title without credentials or embedded instructions")
        from hermes_constants import get_hermes_home
        home=get_hermes_home().resolve();path=home/"state.db"
        if not path.is_file() or path.stat().st_size==0:
            raise ValueError("The active chat has not been persisted yet; try again after its first message")
        if path.resolve().parent!=home:
            raise ValueError("The active chat store is outside this profile")
        db=SessionDB(path)
        try:
            current=db.get_session(session_id)
            if current is None:raise ValueError("The active chat is not in this profile")
            old_title,old_source=current.get("title"),current.get("title_source")
            if old_title==title:
                return json.dumps({"success":True,"title":title,"changed":False})
            if current.get("hidden") and old_title==db.CANONICAL_BOT_CHAT_TITLE:
                raise ValueError("The canonical bot chat keeps its identifying name")
            human=bool(old_title and old_source not in (db.TITLE_SOURCE_DERIVED,db.TITLE_SOURCE_LLM))
            if human:
                from tools.approval import request_tool_approval
                decision=request_tool_approval("rename_current_chat",
                    f"Replace your chosen chat title {old_title!r} with {title!r} in this chat?",
                    rule_key="chat-title:replace-user-name",require_human_once=True)
                if decision.get("approved") is not True:
                    return json.dumps({"error":"The existing chat title was kept; replacement needs fresh human approval.","changed":False})
            audit=current_workspace.audit;operation=uuid.uuid4().hex
            digest=lambda text:hashlib.sha256((text or "").encode()).hexdigest()
            audit.append("chat.rename_requested",{"operation":operation,"session":session_id,"previous_hash":digest(old_title),"requested_hash":digest(title),"human_approved":human})
            candidate=title
            for attempt in range(8):
                try:
                    audit.append("chat.rename_candidate",{"operation":operation,"session":session_id,"candidate_hash":digest(candidate)})
                    changed=db.compare_and_set_session_title(session_id,candidate,expected_title=old_title,
                        expected_source=old_source,source=db.TITLE_SOURCE_USER if human else db.TITLE_SOURCE_LLM)
                    break
                except ValueError:
                    # Resolve only actual name collisions; validation/identity errors
                    # must never turn into a retry that modifies another chat.
                    if not db.get_session_by_title(candidate):raise
                    candidate=db.get_next_title_in_lineage(title)
                    candidate=db.sanitize_title(candidate)
            else:raise ValueError("Could not allocate a unique title; choose another name")
            if not changed:
                audit.append("chat.rename_stale",{"operation":operation,"session":session_id})
                return json.dumps({"error":"The chat name changed during review. Read the current title before trying again.","changed":False})
            recorded=True
            try:
                audit.append("chat.renamed",{"operation":operation,"session":session_id,"title_hash":digest(candidate),"human_approved":human,"tool":"rename_current_chat"})
            except Exception:
                # The intent is already durable; do not misreport a saved rename as
                # an unchanged chat if the separate receipt store is unavailable.
                recorded=False
            notified=False
            try:
                from gateway.session_context import get_session_env
                from tools.desktop_ui import emit
                if get_session_env("HERMES_UI_SESSION_ID",""):
                    notified=emit("session.title",{"session_id":session_id,"title":candidate})
            except Exception:pass
            return json.dumps({"success":True,"title":candidate,"changed":True,"live_update":notified,"audit_recorded":recorded,
                               **({"warning":"Title saved, but its Audit completion receipt could not be persisted."} if not recorded else {})},ensure_ascii=False)
        finally:db.close()
    except (ValueError,PermissionError,OSError) as error:
        return json.dumps({"error":str(error),"changed":False})


def register(ctx):
    ctx.register_tool(name="rename_current_chat",toolset="file",schema=SCHEMA,handler=rename,check_fn=available,
                      description="Rename the current local chat",emoji="✎")
