"""Local, reviewable document lifecycle metadata and bounded conflict hints.

Extracted fields are suggestions. Only a deliberate review marks a source current;
similarity and number changes flag potential disagreements, not semantic proof.
"""
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re

FIELDS = {"family":120, "version":40, "owner":120, "effective_date":10, "review_due":10}

def today_utc():
    return datetime.now(timezone.utc).date().isoformat()


def defaults(filename):
    stem = Path(filename).stem
    stem = re.sub(r"\.(?:pdf|docx|xlsx|pptx)$", "", stem, flags=re.I)
    stem = re.sub(r"[ _.-]v\d+(?:\.\d+)*$", "", stem, flags=re.I)
    return {"family":stem[:120], "version":"", "owner":"", "effective_date":"", "review_due":"",
            "status":"unreviewed", "superseded_by":""}


def validate(value):
    result = {}
    for field, maximum in FIELDS.items():
        item = value.get(field, "")
        if not isinstance(item, str) or len(item)>maximum or any(ord(c)<32 for c in item):
            raise ValueError(f"Invalid document {field}")
        item = item.strip()
        if field in {"effective_date", "review_due"} and item:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", item):
                raise ValueError("Document dates must use YYYY-MM-DD")
            date.fromisoformat(item)
        result[field] = item
    if not result["family"]:
        raise ValueError("Document family is required")
    result["status"] = value.get("status", "unreviewed")
    result["superseded_by"] = value.get("superseded_by", "")
    if result["status"] not in {"unreviewed", "current", "superseded"}:
        raise ValueError("Invalid document review status")
    if result["status"] == "superseded":
        if not re.fullmatch(r"[a-f0-9]{32}", str(result["superseded_by"])):
            raise ValueError("Choose a current replacement document")
    elif result["superseded_by"]:
        raise ValueError("Only superseded documents may have a replacement")
    return result


def extracted(filename, text, previous=None, unchanged=False):
    result = defaults(filename)
    if previous:
        result.update({key:previous[key] for key in result if key in previous})
    if unchanged:
        return validate(result)
    # Known scalar header lines only. No YAML evaluation or model call.
    aliases = {"document":"family", "title":"family", "version":"version", "owner":"owner",
               "effective date":"effective_date", "effective":"effective_date", "review due":"review_due"}
    for line in text[:4000].splitlines()[:50]:
        match = re.fullmatch(r"\s*(Document|Title|Version|Owner|Effective date|Effective|Review due):\s*(.+?)\s*", line, re.I)
        if match:
            key = aliases[match[1].lower()]
            item = match[2][:FIELDS[key]]
            try:
                validate({**result,key:item})
            except ValueError:
                continue
            result[key] = item
    if result["status"] != "superseded":
        result["status"] = "unreviewed"
        result["superseded_by"] = ""
    return validate(result)


def public(metadata, filename, content_hash, today=None):
    value = validate({**defaults(filename), **metadata.get("governance", {})})
    today = today or today_utc()
    value["revision"] = hashlib.sha256(json.dumps([content_hash,value],sort_keys=True).encode()).hexdigest()
    value["warnings"] = []
    if value["status"] == "unreviewed": value["warnings"].append("unreviewed")
    if value["effective_date"] and value["effective_date"]>today: value["warnings"].append("not_yet_effective")
    if value["review_due"] and value["review_due"]<today: value["warnings"].append("review_overdue")
    if value["status"] == "superseded": value["warnings"].append("superseded")
    return value


def review(engine, doc_id, value, expected_revision):
    clean = validate(value)
    if not re.fullmatch(r"[a-f0-9]{32}", str(doc_id)):
        raise ValueError("Invalid document ID")
    if not re.fullmatch(r"[a-f0-9]{64}", str(expected_revision)):
        raise ValueError("Reload the document before reviewing")
    with engine.lock, engine._connection() as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            row = db.execute("SELECT * FROM rag_documents WHERE doc_id=?",(doc_id,)).fetchone()
            if not row: raise ValueError("Document not found")
            metadata = json.loads(row["metadata_json"])
            current = public(metadata,row["filename"],row["content_hash"])
            if current["revision"] != expected_revision:
                raise ValueError("Document changed. Reload and review it again.")
            if clean["status"] == "current":
                if clean["effective_date"] and clean["effective_date"]>today_utc():
                    raise ValueError("A future document cannot be marked current yet")
                if db.execute("SELECT 1 FROM rag_quarantine WHERE doc_id=?",(doc_id,)).fetchone():
                    raise ValueError("A quarantined document cannot be approved")
            if clean["status"] == "superseded":
                if clean["superseded_by"] == doc_id: raise ValueError("A document cannot replace itself")
                target = db.execute("SELECT * FROM rag_documents WHERE doc_id=?",(clean["superseded_by"],)).fetchone()
                if not target: raise ValueError("Replacement is not in this collection")
                other = public(json.loads(target["metadata_json"]),target["filename"],target["content_hash"])
                if other["status"] != "current" or "not_yet_effective" in other["warnings"] or other["family"].casefold()!=clean["family"].casefold():
                    raise ValueError("Choose a reviewed current replacement from the same document family")
                if db.execute("SELECT 1 FROM rag_quarantine WHERE doc_id=?",(target["doc_id"],)).fetchone():
                    raise ValueError("A quarantined document cannot replace another source")
                # Prevent reactivating a historical replacement into a cycle.
                seen={doc_id}; cursor=target
                while cursor:
                    if cursor["doc_id"] in seen: raise ValueError("Replacement cycle is not allowed")
                    seen.add(cursor["doc_id"])
                    next_id=json.loads(cursor["metadata_json"]).get("governance",{}).get("superseded_by")
                    cursor=db.execute("SELECT * FROM rag_documents WHERE doc_id=?",(next_id,)).fetchone() if next_id else None
            metadata["governance"] = clean
            db.execute("UPDATE rag_documents SET metadata_json=? WHERE doc_id=?",(json.dumps(metadata),doc_id))
            db.commit()
        except Exception:
            db.rollback(); raise
    return public(metadata,row["filename"],row["content_hash"])


def digest(engine, maximum=200):
    with engine._connection() as db:
        total=db.execute("SELECT COUNT(*) FROM rag_documents").fetchone()[0]
        rows=db.execute("SELECT d.*,substr((SELECT text FROM rag_chunks c WHERE c.doc_id=d.doc_id ORDER BY chunk_index LIMIT 1),1,8000) AS sample FROM rag_documents d WHERE d.doc_id NOT IN (SELECT doc_id FROM rag_quarantine) ORDER BY updated_at DESC,doc_id LIMIT ?",(maximum,)).fetchall()
    sources=[]; issues=[]
    for row in rows:
        governance=public(json.loads(row["metadata_json"]),row["filename"],row["content_hash"])
        source={"doc_id":row["doc_id"],"filename":row["filename"],"governance":governance}
        if governance["warnings"]:
            issues.append({"kind":"document_review","documents":[source],"warnings":governance["warnings"],"owner":governance["owner"]})
        if governance["status"] == "superseded": continue
        # Metadata headers must not dominate the similarity calculation.
        sample=re.sub(r"(?im)^\s*(?:Document|Title|Version|Owner|Effective(?: date)?|Review due):[^\n]*", "",row["sample"] or "")
        tokens=set(re.findall(r"[^\W\d_]{2,}", sample.casefold(),re.UNICODE))
        numbers=set(re.findall(r"\b\d+(?:\.\d+)?\b",sample))
        for old,old_tokens,old_numbers,old_hash in sources:
            same_family=bool(governance["family"] and governance["family"].casefold()==old["governance"]["family"].casefold())
            overlap=len(tokens&old_tokens)/max(1,len(tokens|old_tokens))
            duplicate=row["content_hash"]==old_hash
            if duplicate or same_family or (len(tokens)>=8 and len(old_tokens)>=8 and overlap>=.7):
                changed_numbers=numbers!=old_numbers and bool(numbers or old_numbers)
                issues.append({"kind":"duplicate" if duplicate else "potential_conflict" if changed_numbers else "related_versions",
                               "documents":[old,source],"similarity":round(overlap,3),"numeric_difference":changed_numbers,
                               "owner":governance["owner"] or old["governance"]["owner"]})
            if len(issues)>=400: break
        sources.append((source,tokens,numbers,row["content_hash"]))
        if len(issues)>=400: break
    return {"issues":issues[:400],"scanned_documents":len(rows),"total_documents":total,"bounded":total>len(rows) or len(issues)>=400,
            "method":"Checks declared source details and similar first passages for changed numbers. Potential conflicts require human review.",
            "delivery":"Local review digest only. No owner messages are sent."}


def source_preview(engine, doc_id):
    if not re.fullmatch(r"[a-f0-9]{32}",str(doc_id)):
        raise ValueError("Invalid document ID")
    with engine._connection() as db:
        row=db.execute("SELECT * FROM rag_documents WHERE doc_id=?",(doc_id,)).fetchone()
        if not row: raise ValueError("Document not found")
        parts=[]; length=0
        for chunk in db.execute("SELECT text FROM rag_chunks WHERE doc_id=? ORDER BY chunk_index LIMIT 20",(doc_id,)):
            parts.append(chunk["text"]);length+=len(chunk["text"])+2
            if length>16000: break
    metadata=json.loads(row["metadata_json"])
    return {"filename":row["filename"],"text":"\n\n".join(parts)[:16000],"truncated":length>16000 or row["chunk_count"]>len(parts),
            "governance":public(metadata,row["filename"],row["content_hash"]),"safety":metadata.get("safety",{}),
            "notice":"Stored passages, with possible overlap, shown as inert untrusted text. This preview is not sent to a model."}
