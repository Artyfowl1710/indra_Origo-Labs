"""Local conversation annotations, separate from the model's cached history."""
from contextlib import closing
from datetime import datetime,timezone
import re,sqlite3
from pathlib import Path
from app.sqlite_safety import open_database

def identity(value):
    if not isinstance(value,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}",value):raise ValueError("Invalid conversation or record ID")
    return value

class ConversationRecords:
    def __init__(self,root):
        self.path=Path(root)/"conversation-records.sqlite3";self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(self.connect()) as db:
            db.execute("CREATE TABLE IF NOT EXISTS records(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE,chat TEXT,kind TEXT,role TEXT,text TEXT,model TEXT,provider TEXT,source TEXT,created TEXT)")
            db.execute("CREATE INDEX IF NOT EXISTS records_chat_seq ON records(chat,seq)");db.commit()
    def connect(self):
        db=open_database(self.path,prefer_wal=False,timeout=15);db.row_factory=sqlite3.Row;return db
    def save(self,chat,entries,source="client"):
        identity(chat)
        if not isinstance(entries,list) or not 1<=len(entries)<=50:raise ValueError("Save 1–50 records at a time")
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            for row in entries:
                key=identity(row.get("id"));kind=row.get("kind","voice");role=row.get("role","note");text=row.get("text","")
                if kind not in {"voice","note","action"} or role not in {"user","assistant","note"} or not isinstance(text,str) or not 1<=len(text)<=16000:raise ValueError("Invalid conversation entry")
                if source=="client" and kind=="action":raise ValueError("Runtime action records cannot be supplied by clients")
                model=str(row.get("model") or "")[:160];provider=str(row.get("provider") or "")[:160]
                previous=db.execute("SELECT chat,created,source FROM records WHERE id=?",(key,)).fetchone()
                if previous and previous["chat"]!=chat:raise ValueError("Record belongs to a different conversation")
                if previous and previous["source"]=="runtime" and source!="runtime":raise ValueError("Runtime records cannot be overwritten by clients")
                created=previous["created"] if previous else datetime.now(timezone.utc).isoformat()
                db.execute("INSERT OR REPLACE INTO records(id,chat,kind,role,text,model,provider,source,created) VALUES(?,?,?,?,?,?,?,?,?)",(key,chat,kind,role,text,model,provider,source,created))
            db.commit()
    def list(self,chat,after=0,limit=200):
        identity(chat)
        if after<0:raise ValueError("Invalid record cursor")
        with closing(self.connect()) as db:return [dict(row) for row in db.execute("SELECT * FROM records WHERE chat=? AND seq>? ORDER BY seq LIMIT ?",(chat,after,max(1,min(limit,200))))]
