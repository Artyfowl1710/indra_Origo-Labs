"""Bounded, offline parsing of user-selected memory exports.

Imports are candidates, never executable instructions. No model or external API
is used here; the user must select facts before they enter personal context.
"""
import hashlib
import json
import re
import time
import uuid
from contextlib import contextmanager

from filelock import FileLock

from app.content_safety import scan_document

MAX_EXPORT_BYTES = 128 * 1024
MAX_FACTS = 20
SECRET = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{20,}|"
    r"(?:api[_ -]?key|password|access[_ -]?token|secret)\s*[:=]\s*\S+)",
    re.IGNORECASE,
)


def clean_identity(value):
    if not isinstance(value, dict):
        raise ValueError("Personal memory must be an object")
    result = {}
    for field, limit in (("name", 80), ("instructions", 2000), ("interests", 300)):
        text = value.get(field, "")
        if not isinstance(text, str) or len(text) > limit:
            raise ValueError(f"Invalid {field}: maximum {limit} characters")
        result[field] = text.strip()
    facts = value.get("facts", [])
    if not isinstance(facts, list) or len(facts) > MAX_FACTS:
        raise ValueError("Keep at most 20 personal facts")
    if any(not isinstance(fact, str) or not fact.strip() or len(fact) > 400 for fact in facts):
        raise ValueError("Personal facts must contain 1–400 characters")
    result["facts"] = list(dict.fromkeys(fact.strip() for fact in facts))
    for field in ("share_across_profiles", "setup_complete"):
        flag = value.get(field, False)
        if not isinstance(flag, bool):
            raise ValueError(f"Invalid {field}")
        result[field] = flag
    # Preserve the consent behaviour of pre-existing, manually saved memories.
    flag = value.get("use_in_requests", bool(result["name"] or result["instructions"]))
    if not isinstance(flag, bool):
        raise ValueError("Invalid use_in_requests")
    result["use_in_requests"] = flag
    return result


def revision(value):
    return hashlib.sha256(json.dumps(clean_identity(value), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def candidates(raw):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_EXPORT_BYTES:
        raise ValueError("Choose a UTF-8 text or JSON memory export up to 128 KiB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError:
        raise ValueError("Memory export must be UTF-8 text or JSON") from None
    if "\x00" in text:
        raise ValueError("Binary files are not memory exports")
    if text.lstrip().startswith(("{", "[")):
        try:
            def unique(pairs):
                result = {}
                for key, item in pairs:
                    if key in result:
                        raise ValueError("Duplicate JSON fields")
                    result[key] = item
                return result
            value = json.loads(text, object_pairs_hook=unique)
        except (ValueError, RecursionError):
            raise ValueError("Invalid memory JSON") from None
        if isinstance(value, dict):
            value = value.get("memories", value.get("facts"))
        if not isinstance(value, list):
            raise ValueError("Choose a list of memories, not a full conversation export")
        lines = []
        for item in value:
            if isinstance(item, dict):
                if any(key in item for key in ("role", "messages", "mapping", "chat_messages")):
                    raise ValueError("Export saved memories as text or a memories list, not whole chats")
                item = item.get("text", item.get("content"))
            if not isinstance(item, str):
                raise ValueError("Each memory must be text")
            lines.append(item)
    else:
        lines = text.splitlines()
    if len(lines) > 100:
        raise ValueError("Review at most 100 memory candidates at a time")
    result = []
    for line in dict.fromkeys(line.strip().lstrip("-*• ") for line in lines):
        if not line:
            continue
        decision = scan_document(line)
        reasons = list(decision["rules"])
        if len(line) > 400:
            reasons.append("fact_too_long")
        if SECRET.search(line) or "PRIVATE KEY-----" in line:
            reasons.append("possible_secret")
            line = "[Hidden: possible credential. Remove it from the export before importing.]"
        result.append({"id": str(len(result)), "text": line[:400], "blocked": bool(reasons), "reasons": reasons})
    if not result:
        raise ValueError("No memories found in this file")
    return result


SHARED_FIELDS = ("name", "instructions", "interests", "facts")


def read_identity(workspace, db=None):
    if db is None:
        with workspace.db() as connection:
            return read_identity(workspace, connection)
    row = db.execute("SELECT value FROM preferences WHERE id='identity'").fetchone()
    try:
        value = clean_identity(json.loads(row["value"]) if row else {})
        path = workspace.shared_root / "shared-user-memory.json"
        if value["share_across_profiles"] and path.is_file():
            with path.open("rb") as stream:
                raw = stream.read(16385)
            if len(raw) > 16384:
                raise ValueError("Shared personal memory exceeds the size limit")
            shared = clean_identity(json.loads(raw))
            value.update({key: shared[key] for key in SHARED_FIELDS})
    except (ValueError, TypeError, UnicodeError):
        raise ValueError("Personal memory could not be read. Repair it in this profile before use.") from None
    return {**value, "revision": revision(value)}


@contextmanager
def memory_lock(workspace):
    workspace.shared_root.mkdir(parents=True, exist_ok=True)
    with workspace.lock, FileLock(str(workspace.shared_root / "shared-user-memory.lock"), timeout=15):
        yield


def save_identity(workspace, value, expected_revision=None, import_id=None, selected=None):
    with memory_lock(workspace):
        path = workspace.shared_root / "shared-user-memory.json"
        previous_shared = None
        wrote_shared = False
        try:
            with workspace.db() as db:
                db.execute("BEGIN IMMEDIATE")
                current = read_identity(workspace, db)
                if expected_revision is not None and current["revision"] != expected_revision:
                    raise ValueError("Personal memory changed. Reload and review your changes again.")
                if import_id is not None:
                    row = db.execute("SELECT value FROM preferences WHERE id=?", ("memory-import:" + import_id,)).fetchone()
                    if not row:
                        raise ValueError("Import preview is missing or already used. Choose the file again.")
                    preview = json.loads(row["value"])
                    if preview["expires"] < time.time() or preview["revision"] != current["revision"]:
                        raise ValueError("Import preview expired or personal memory changed. Review the file again.")
                    if not isinstance(selected, list) or not 1 <= len(selected) <= MAX_FACTS or len(set(selected)) != len(selected):
                        raise ValueError("Select 1–20 distinct memories")
                    by_id = {item["id"]: item for item in preview["candidates"]}
                    if any(key not in by_id or by_id[key]["blocked"] for key in selected):
                        raise ValueError("A selected memory is unavailable or quarantined")
                    value = {**current, "facts": list(dict.fromkeys(current["facts"] + [by_id[key]["text"] for key in selected]))}
                clean = clean_identity(value)
                if clean["share_across_profiles"]:
                    previous_shared = path.read_bytes() if path.is_file() else None
                    temporary = path.with_name("shared-user-memory." + uuid.uuid4().hex + ".tmp")
                    try:
                        temporary.write_text(json.dumps({key: clean[key] for key in SHARED_FIELDS}), encoding="utf-8")
                        temporary.replace(path)
                        wrote_shared = True
                    finally:
                        temporary.unlink(missing_ok=True)
                db.execute("INSERT OR REPLACE INTO preferences VALUES('identity',?)", (json.dumps(clean),))
                if import_id is not None:
                    db.execute("DELETE FROM preferences WHERE id=?", ("memory-import:" + import_id,))
        except Exception:
            # Compensate the file update if the local SQLite transaction failed.
            if wrote_shared:
                if previous_shared is None:
                    path.unlink(missing_ok=True)
                else:
                    temporary = path.with_name("shared-user-memory.restore.tmp")
                    temporary.write_bytes(previous_shared)
                    temporary.replace(path)
            raise
    workspace.audit.append("memory.imported" if import_id else "memory.updated", {
        "content_hash": revision(clean), "facts": len(clean["facts"]),
        "use_in_requests": clean["use_in_requests"], "shared": clean["share_across_profiles"],
    })
    return {**clean, "revision": revision(clean)}


def preview_import(workspace, raw):
    items = candidates(raw)
    now = time.time()
    with memory_lock(workspace), workspace.db() as db:
        db.execute("BEGIN IMMEDIATE")
        for row in db.execute("SELECT id,value FROM preferences WHERE id LIKE 'memory-import:%'").fetchall():
            if json.loads(row["value"])["expires"] < now:
                db.execute("DELETE FROM preferences WHERE id=?", (row["id"],))
        count = db.execute("SELECT COUNT(*) FROM preferences WHERE id LIKE 'memory-import:%'").fetchone()[0]
        if count >= 8:
            raise ValueError("Too many pending imports. Wait 15 minutes before trying again.")
        value = {"id": uuid.uuid4().hex, "expires": now + 900, "revision": read_identity(workspace, db)["revision"],
                 "candidates": items, "source_hash": hashlib.sha256(raw).hexdigest()}
        db.execute("INSERT INTO preferences VALUES(?,?)", ("memory-import:" + value["id"], json.dumps(value)))
    workspace.audit.append("memory.import_previewed", {"source_hash": value["source_hash"], "candidates": len(items), "blocked": sum(item["blocked"] for item in items)})
    return value
