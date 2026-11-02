"""
Admin key management endpoints.
POST /v1/admin/keys
GET  /v1/admin/keys
DELETE /v1/admin/keys/{key_id}
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from server.core.auth import generate_key, hash_key, require_admin
from server.core.schemas import KeyCreateRequest, KeyCreateResponse, KeyListItem
from server.db import ApiKey, get_db

import secrets

router = APIRouter(prefix="/v1/admin/keys", tags=["admin-keys"])


@router.post("", response_model=KeyCreateResponse)
def create_key(
    req: KeyCreateRequest,
    db: Session = Depends(get_db),
    _: ApiKey = Depends(require_admin),
):
    plaintext = generate_key()
    key_id = secrets.token_hex(8)
    row = ApiKey(
        key_id=key_id,
        key_hash=hash_key(plaintext),
        owner=req.owner,
        scope=req.scope,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    return KeyCreateResponse(api_key=plaintext)


@router.get("", response_model=list[KeyListItem])
def list_keys(
    db: Session = Depends(get_db),
    _: ApiKey = Depends(require_admin),
):
    rows = db.query(ApiKey).all()
    return [
        KeyListItem(
            id=r.key_id,
            owner=r.owner,
            scope=r.scope,
            created_at=r.created_at,
            last_used_at=r.last_used_at,
            revoked=r.revoked,
        )
        for r in rows
    ]


@router.delete("/{key_id}", status_code=204)
def revoke_key(
    key_id: str,
    db: Session = Depends(get_db),
    _: ApiKey = Depends(require_admin),
):
    row = db.query(ApiKey).filter(ApiKey.key_id == key_id).first()
    if row is None:
        raise HTTPException(404, "Key not found")
    row.revoked = True
    db.commit()


from pydantic import BaseModel
from typing import Optional


class ContextConfigRequest(BaseModel):
    context_length: int
    preset: Optional[str] = None
    kv_quant: Optional[str] = "q4_0"


@router.post("/context")
def set_server_context(req: ContextConfigRequest):
    """Dynamically reconfigures server context size and KV cache quantization."""
    import subprocess
    import sys
    from pathlib import Path

    script_path = Path(__file__).resolve().parent.parent.parent.parent / "auto-configure-models.py"
    cmd = [sys.executable, str(script_path), "--ctx", str(req.context_length)]
    if req.kv_quant:
        cmd.extend(["--kv-quant", req.kv_quant])
    if req.preset:
        cmd.extend(["--preset", req.preset])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return {
            "ok": proc.returncode == 0,
            "context_length": req.context_length,
            "kv_quant": req.kv_quant,
            "output": proc.stdout or proc.stderr,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/context")
def get_server_context():
    """Returns the currently active context size and KV quantization from llama-swap.yaml."""
    from pathlib import Path
    import re

    cfg = Path(__file__).resolve().parent.parent.parent.parent / "config" / "llama-swap.yaml"
    ctx = 32768
    kv = "q4_0"
    if cfg.exists():
        text = cfg.read_text(encoding="utf-8")
        m_ctx = re.search(r"--ctx-size\s+(\d+)", text)
        if m_ctx:
            ctx = int(m_ctx.group(1))
        m_kv = re.search(r"--cache-type-k\s+([a-zA-Z0-9_]+)", text)
        if m_kv:
            kv = m_kv.group(1)
    return {"context_length": ctx, "kv_quant": kv}

