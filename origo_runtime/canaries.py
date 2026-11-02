"""Hash-only, machine-local canary registry. No external services or classifiers."""
import base64
from contextlib import contextmanager
import hashlib
from pathlib import Path
import re
import secrets
import sqlite3
import time
import unicodedata
from urllib.parse import unquote
from app.sqlite_safety import open_database

TOKEN = re.compile(r"INDRA_CANARY_[A-Za-z0-9_-]{43}")
ENCODED = re.compile(r"(?<![A-Za-z0-9_+/=-])[A-Za-z0-9_+/-]{40,4096}={0,2}(?![A-Za-z0-9_+/=-])")
MAX_SCAN_CHARS = 32 * 1024 * 1024


class CanaryScanError(ValueError):
    """A configured registry could not safely inspect this request."""


class CanaryRegistry:
    def __init__(self, shared_root):
        root = Path(shared_root) / "security"
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "canaries.sqlite3"
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS canaries(id TEXT PRIMARY KEY,digest TEXT UNIQUE NOT NULL,owner TEXT NOT NULL,label TEXT NOT NULL,created REAL NOT NULL)")

    @contextmanager
    def db(self):
        db = open_database(self.path, timeout=10)
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def validate_label(label):
        if not isinstance(label, str) or not re.fullmatch(r"[\w .-]{1,64}", label):
            raise ValueError("Canary label must be 1–64 letters, numbers, spaces, dots or hyphens")

    def create(self, owner, label="Vault canary"):
        self.validate_label(label)
        token = "INDRA_CANARY_" + secrets.token_urlsafe(32)
        ident = secrets.token_hex(16)
        with self.db() as db:
            db.execute("INSERT INTO canaries VALUES(?,?,?,?,?)", (ident, hashlib.sha256(token.encode()).hexdigest(), str(owner), label, time.time()))
        # Token is returned once; the registry retains only its hash.
        return {"id": ident, "token": token}

    def list(self, owner):
        with self.db() as db:
            return [dict(zip(("id", "label", "created"), row)) for row in db.execute("SELECT id,label,created FROM canaries WHERE owner=? ORDER BY created DESC", (str(owner),))]

    def matches(self, payload):
        with self.db() as db:
            known = dict(db.execute("SELECT digest,id FROM canaries"))
        if not known:
            return []
        # Iterate leaves without serializing credentials or retaining full payload copies.
        stack = [(payload, 0)]; budget = MAX_SCAN_CHARS; found = set(); nodes = 0
        while stack:
            value, depth = stack.pop(); nodes += 1
            if nodes > 200_000 or depth > 80:
                raise CanaryScanError("Canary scan structure limit exceeded")
            if isinstance(value, dict):
                stack.extend((v, depth + 1) for v in value.values())
                stack.extend((k, depth + 1) for k in value.keys())
            elif isinstance(value, (list, tuple)):
                stack.extend((v, depth + 1) for v in value)
            elif isinstance(value, str):
                budget -= len(value)
                if budget < 0:
                    raise CanaryScanError("Canary scan size limit exceeded")
                normalized = unicodedata.normalize("NFKC", value)
                normalized = "".join(c for c in normalized if not c.isspace() and unicodedata.category(c) != "Cf")
                variants = [(value, 0), (normalized, 0)]
                while variants:
                    text, level = variants.pop()
                    for token in TOKEN.findall(text):
                        ident = known.get(hashlib.sha256(token.encode()).hexdigest())
                        if ident:
                            found.add(ident)
                    if level >= 2:
                        continue
                    decoded = unquote(text)
                    if decoded != text:
                        budget -= len(decoded); variants.append((decoded, level + 1))
                    # SDKs serialize literal strings themselves; explicit JSON escape obfuscation
                    # in tool/web evidence is also common. Decode escapes, never evaluate code.
                    escaped = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m[1], 16)), text)
                    if escaped != text:
                        budget -= len(escaped); variants.append((escaped, level + 1))
                    for candidate in ENCODED.findall(text):
                        try:
                            raw = base64.b64decode(candidate + "=" * (-len(candidate) % 4), altchars=b"-_", validate=True)
                            decoded = raw.decode("utf-8")
                        except (ValueError, UnicodeError):
                            continue
                        budget -= len(decoded); variants.append((decoded, level + 1))
                    if budget < 0:
                        raise CanaryScanError("Canary scan decoding limit exceeded")
        return sorted(found)

    def veto(self, payload, audit, *, channel, session="", turn=""):
        matches = self.matches(payload)
        if not matches:
            return None
        # No source text, URL, command, key, label or canary value enters Audit.
        audit.append("security.canary_blocked", {"canary_ids": matches, "channel": channel,
                     "session": str(session)[:240], "turn": str(turn)[:240]})
        return {"action": "block", "message": "Transmission stopped: protected vault canary detected. See Audit for the incident."}
