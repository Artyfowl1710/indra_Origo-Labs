"""Transactional SHA-256 event chain with Ed25519 signatures and portable checkpoints."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from contextlib import contextmanager
from filelock import FileLock
from app.sqlite_safety import open_database
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

_key_lock = threading.Lock()

def canonical(value): return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

class AuditLog:
    def __init__(self, home):
        self.root = Path(home) / "provenance"; self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "events.sqlite3"
        with _key_lock, FileLock(str(self.root / "signing-key.lock")):
            keypath = self.root / "signing-key.pem"
            if not keypath.exists():
                key = Ed25519PrivateKey.generate()
                try:
                    with keypath.open("xb") as file:
                        file.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
                except FileExistsError: pass
            self.key = serialization.load_pem_private_key(keypath.read_bytes(), password=None)
        self.public = self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, event TEXT NOT NULL, digest TEXT NOT NULL, signature TEXT NOT NULL)")

    @contextmanager
    def connect(self):
        db = open_database(self.path, timeout=15); db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback(); raise
        finally: db.close()

    def append(self, kind, payload):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            last = db.execute("SELECT seq,digest FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            record = {"seq":last["seq"]+1 if last else 1, "previous":last["digest"] if last else "0"*64,
                      "time":datetime.now(timezone.utc).isoformat(), "kind":kind, "payload":payload}
            digest = hashlib.sha256(canonical(record)).hexdigest()
            signature = self.key.sign(bytes.fromhex(digest)).hex()
            db.execute("INSERT INTO events VALUES(?,?,?,?)", (record["seq"], canonical(record).decode(), digest, signature))
        return {**record,"hash":digest,"signature":signature}

    def verify(self):
        previous = "0"*64; count = 0
        public = Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.public))
        with self.connect() as db:
            for row in db.execute("SELECT * FROM events ORDER BY seq"):
                try:
                    event = json.loads(row["event"])
                    if event["seq"] != count+1 or row["seq"] != count+1 or event["previous"] != previous:
                        raise ValueError("Audit sequence or previous digest mismatch")
                    digest = hashlib.sha256(canonical(event)).hexdigest()
                    if digest != row["digest"]:
                        raise ValueError("Audit event digest mismatch")
                    public.verify(bytes.fromhex(row["signature"]), bytes.fromhex(digest))
                except Exception as exc:
                    return {"valid":False,"checked":count,"first_invalid":row["seq"],"error":type(exc).__name__}
                count += 1; previous = digest
        head = {"count":count,"head":previous,"public_key":self.public}
        return {"valid":True, **head, "checkpoint_signature":self.key.sign(canonical(head)).hex()}

    def recent(self, limit=100):
        with self.connect() as db:
            return [{**json.loads(row["event"]),"hash":row["digest"],"signature":row["signature"]}
                    for row in db.execute("SELECT * FROM events ORDER BY seq DESC LIMIT ?",(min(max(limit,1),200),))]
