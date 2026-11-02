"""Profile/turn-scoped content exposure ledger and bounded result screening."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import time

from app.content_safety import scan_document, MAX_SCAN_CHARS, SCANNER_VERSION
from .audit import AuditLog
from app.sqlite_safety import open_database

# Only local, read-only retrieval is exempt from escalation. Network reads can
# themselves send sensitive query/URL data; new/unknown tools are not assumed safe.
READ_ONLY_TOOLS = frozenset({"read_file","search_files","list_directory","knowledge_search",
                           "session_search","session_read","skills_list","skill_view"})


def argument_digest(args):
    return hashlib.sha256(json.dumps(args,sort_keys=True,default=str).encode()).hexdigest()


def contains_evidence(user_message, history):
    markers=("<document_evidence>","<image_evidence>","<untrusted_content>")
    if isinstance(user_message,str) and any(m in user_message for m in markers):
        return True
    if not isinstance(history,list):return False
    media={"image_url","input_image","input_audio","audio_url","video_url"}
    for row in history:
        if not isinstance(row,dict):continue
        if row.get("role")=="tool":return True
        content=row.get("content")
        if isinstance(content,str) and any(m in content for m in markers):return True
        if isinstance(content,list) and any(isinstance(p,dict) and p.get("type") in media for p in content):return True
    return False


class ContentGuard:
    def __init__(self,home):
        self.home=Path(home);self.root=self.home/"workspace-data";self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/"content-guard.sqlite3";self.audit=AuditLog(self.home)
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS exposure(session TEXT NOT NULL,turn TEXT NOT NULL,reason TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(session,turn))")

    @contextmanager
    def db(self):
        db=open_database(self.path,timeout=10)
        try:yield db;db.commit()
        except Exception:db.rollback();raise
        finally:db.close()

    @staticmethod
    def scoped(session,turn):
        return isinstance(session,str) and isinstance(turn,str) and 0<len(session)<=240 and 0<len(turn)<=240

    def mark(self,session,turn,reason):
        if not self.scoped(session,turn):return
        with self.db() as db:
            # Each entry describes one turn, not a permanent trust judgment.
            db.execute("DELETE FROM exposure WHERE created<?",(time.time()-7*86400,))
            inserted=db.execute("INSERT OR IGNORE INTO exposure VALUES(?,?,?,?)",(session,turn,reason[:160],time.time())).rowcount
        if inserted:self.audit.append("security.untrusted_context",{"session":session,"turn":turn,"reason":reason[:160]})

    def exposed(self,session,turn):
        if not self.scoped(session,turn):return True
        with self.db() as db:return db.execute("SELECT 1 FROM exposure WHERE session=? AND turn=?",(session,turn)).fetchone() is not None

    def before_tool(self,tool,args,session,turn,call=""):
        risky=tool not in READ_ONLY_TOOLS
        review=risky and self.exposed(session,turn)
        # Mark before dispatch, so concurrent results cannot arrive without an
        # exposure record. A failed read remains conservatively marked.
        self.mark(session,turn,"tool result pending: "+tool)
        if not review:return None
        if not self.scoped(session,turn):
            return {"action":"block","message":"Untrusted-content review requires an attributable session and turn. Start a new chat and retry."}
        from app.rag import _redact
        details={k:_redact(str(v))[0][:500] for k,v in args.items() if k in {
            "command","path","file_path","target","recipient","to","url","method","amount","action"}}
        digest=argument_digest(args)
        self.audit.append("security.human_review_required",{"session":session,"turn":turn,"tool":tool,
            "tool_call":str(call)[:240],"arguments_hash":digest})
        return {"action":"approve","require_human_once":True,
            "rule_key":"untrusted:"+digest,
            "message":"This turn has read or requested untrusted content. Review this operation before it runs.\nRequested action: "+json.dumps(details,ensure_ascii=False)}

    def screen_result(self,tool,result,session,turn):
        if not isinstance(result,str):return None
        self.mark(session,turn,"tool result: "+tool)
        # Media data URIs are not plain document text. Pixel/audio interpretation
        # needs separate guards; never expand them into a text scanning prompt.
        body=None
        if len(result)>MAX_SCAN_CHARS:
            decision={"version":SCANNER_VERSION,"quarantined":True,"rules":["scan_limit"]}
        else:
            try:body=json.loads(result)
            except (ValueError,TypeError):pass
            pieces=[];length=0;stack=[body if body is not None else result]
            while stack and length<=MAX_SCAN_CHARS:
                value=stack.pop()
                if isinstance(value,dict):stack.extend(value.values());stack.extend(value.keys())
                elif isinstance(value,list):stack.extend(value)
                elif isinstance(value,str) and not value.startswith("data:"):
                    pieces.append(value);length+=len(value)+1
            decision=scan_document("\n".join(pieces))
        evidence={"untrusted":True,"quarantined":decision["quarantined"],"scanner_version":decision["version"]}
        if decision["quarantined"]:
            self.audit.append("security.tool_result_quarantined",{"session":session,"turn":turn,"tool":tool,
                "result_hash":hashlib.sha256(result.encode()).hexdigest(),"rules":decision["rules"]})
            return json.dumps({"error":"Tool content quarantined by the offline instruction scanner.",
                               "_indra_evidence":{**evidence,"rules":decision["rules"]}})
        # Preserve existing JSON keys for tools called from code. Structured
        # media/list results are left in their original format; exposure remains.
        if isinstance(body,dict):return json.dumps({**body,"_indra_evidence":evidence},ensure_ascii=False)
        if body is None:return json.dumps({"content":result,"_indra_evidence":evidence},ensure_ascii=False)
        return None
