"""Profile-scoped public model metadata, shared by discovery and media routing.

No credentials enter this cache. A failed refresh retains a bounded stale copy;
readers used on the inference path never perform network I/O.
"""
from __future__ import annotations

import copy
import json
import threading
import time
from pathlib import Path

TTL = 600
STALE_TTL = 3 * 24 * 3600
RETRY_TTL = 30
_lock = threading.RLock()
_memory: dict[str, dict] = {}
_failed: dict[str, float] = {}
_indices: dict[str, tuple[dict, dict]] = {}
_mtimes: dict[str, int] = {}


def _path() -> Path:
    from hermes_constants import get_hermes_home
    return get_hermes_home() / "cache" / "openrouter-live-models.json"


def _read(path: Path) -> dict:
    key = str(path)
    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        stamp = -1
    if key not in _memory or (stamp != -1 and _mtimes.get(key) != stamp):
        try:
            if path.stat().st_size > 16 * 1024 * 1024:
                return {}
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("version") == 1 and isinstance(data.get("models"), list) and isinstance(data.get("at"), (int, float)):
                _memory[key] = data
                _mtimes[key] = stamp
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    return _memory.get(key, {})


def _valid(entry: dict, ttl: float) -> bool:
    age = time.time() - entry.get("at", 0)
    return bool(entry.get("models")) and 0 <= age < ttl


def _sanitize(items: list) -> list[dict]:
    result = {}
    for item in items[:5000]:
        if not isinstance(item, dict):
            continue
        mid = item.get("id")
        if not isinstance(mid, str) or not mid.strip() or len(mid) > 300:
            continue
        architecture = item.get("architecture") or {}
        if not isinstance(architecture, dict):
            architecture = {}
        modalities = {k: [v for v in architecture.get(k, []) if isinstance(v, str) and len(v) < 32]
                      for k in ("input_modalities", "output_modalities") if isinstance(architecture.get(k), list)}
        pricing = item.get("pricing") or {}
        pricing = {k: str(v)[:80] for k, v in pricing.items() if k in {"prompt", "completion", "image", "request", "input_cache_read"}} if isinstance(pricing, dict) else {}
        params = item.get("supported_parameters")
        result[mid] = {"id": mid, "name": str(item.get("name") or mid)[:300], "architecture": modalities,
                       "pricing": pricing, "supported_parameters": [p for p in params if isinstance(p, str)][:100] if isinstance(params, list) else None,
                       "context_length": item.get("context_length") if isinstance(item.get("context_length"), int) else None}
    return list(result.values())


def models(fetcher=None, *, refresh=False) -> list[dict]:
    """Fetch under one lock (single-flight), or read cached metadata without I/O."""
    from utils import atomic_replace
    with _lock:
        path = _path(); key = str(path); cached = _read(path)
        if not refresh and _valid(cached, TTL):
            return copy.deepcopy(cached["models"])
        if fetcher is not None and (refresh or time.monotonic() - _failed.get(key, -1e9) >= RETRY_TTL):
            try:
                items = fetcher()
                clean = _sanitize(items) if isinstance(items, list) else []
                if not clean:
                    raise ValueError("Empty or invalid model catalog")
                entry = {"version": 1, "at": time.time(), "models": clean}
                _memory[key] = entry; _failed.pop(key, None)
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = path.with_suffix(".tmp")
                    temporary.write_text(json.dumps(entry), encoding="utf-8")
                    atomic_replace(temporary, path)
                    _mtimes[key] = path.stat().st_mtime_ns
                except OSError:
                    pass  # in-memory discovery remains usable on read-only disks
                return copy.deepcopy(clean)
            except Exception:
                _failed[key] = time.monotonic()
        return copy.deepcopy(cached["models"]) if _valid(cached, STALE_TTL) else []


def metadata(model: str) -> dict | None:
    with _lock:
        key = str(_path()); entry = _read(_path())
        if not _valid(entry, STALE_TTL):
            return None
        previous, index = _indices.get(key, (None, {}))
        if previous is not entry:
            index = {m["id"]: m for m in entry["models"] if isinstance(m, dict) and isinstance(m.get("id"), str)}
            _indices[key] = (entry, index)
        return copy.deepcopy(index.get(model))
