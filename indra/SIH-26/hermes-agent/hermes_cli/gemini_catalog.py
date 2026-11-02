"""Native Google model discovery with credential-scoped, bounded caching.

Google returns models[].name and supportedGenerationMethods, not data[].id.
Listing a model does not establish the account's quota or billing entitlement.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import threading
import time
import urllib.parse
import urllib.request

BASE = "https://generativelanguage.googleapis.com/v1beta"
TTL = 600
STALE_TTL = 3 * 86400
_lock = threading.RLock()
_memory: dict[str, tuple[int, dict]] = {}
_failures: dict[str, float] = {}


def credentials() -> tuple[str, str]:
    from hermes_cli.models import _api_key_credentials
    key, base = _api_key_credentials("gemini")
    if not key:
        from hermes_cli.auth import read_credential_pool
        key = next((e.get("access_token", "") for e in read_credential_pool("gemini")
                    if e.get("access_token") and e.get("last_status") != "dead"), "")
    return key, (base or BASE).rstrip("/").removesuffix("/openai")


def _path() -> Path:
    from hermes_constants import get_hermes_home
    return get_hermes_home() / "cache/gemini-live-models.json"


def _read() -> dict:
    path = _path(); identity = str(path)
    try:
        stat = path.stat()
        if stat.st_size > 8 * 1024 * 1024:
            return {}
        if identity not in _memory or _memory[identity][0] != stat.st_mtime_ns:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("models"), list):
                return {}
            _memory[identity] = (stat.st_mtime_ns, data)
    except (OSError, ValueError, TypeError):
        pass
    return _memory.get(identity, (0, {}))[1]


def _fresh(data: dict, ttl: int) -> bool:
    try:
        return 0 <= time.time() - data.get("at", 0) < ttl and bool(data.get("models"))
    except TypeError:
        return False


def _fetch(key: str, base: str) -> list[dict]:
    from hermes_cli.urllib_security import open_credentialed_url
    records = []; page = ""; seen = set()
    for _ in range(20):
        params = {"pageSize": 1000}
        if page: params["pageToken"] = page
        req = urllib.request.Request(base + "/models?" + urllib.parse.urlencode(params),
                                     headers={"x-goog-api-key": key, "Accept": "application/json"})
        with open_credentialed_url(req, timeout=10) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("Model catalog exceeded its size limit")
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get("models"), list):
            raise ValueError("Invalid Google model catalog")
        records.extend(data["models"])
        page = data.get("nextPageToken")
        if not page: return records
        if not isinstance(page, str) or len(page) > 4096 or page in seen:
            raise ValueError("Invalid model pagination")
        seen.add(page)
    raise ValueError("Model catalog pagination limit reached")


def _normalize(rows: list) -> list[dict]:
    result = {}
    for raw in rows[:5000]:
        if not isinstance(raw, dict) or not isinstance(raw.get("name"), str): continue
        mid = raw["name"].removeprefix("models/")
        if not mid or len(mid) > 300 or any(ord(c) < 32 for c in mid): continue
        methods = raw.get("supportedGenerationMethods", [])
        if not isinstance(methods, list): continue
        result[mid] = {"id": mid, "name": str(raw.get("displayName") or mid)[:300],
                       "methods": [m for m in methods if isinstance(m, str)][:30],
                       "context_length": raw.get("inputTokenLimit") if isinstance(raw.get("inputTokenLimit"), int) else None}
    return list(result.values())


def models(*, refresh=False, api_key=None, base_url=None, fetcher=None) -> list[dict]:
    """Native API listing, cached per profile + key/endpoint fingerprint."""
    from utils import atomic_replace
    if api_key is None:
        api_key, resolved_base = credentials()
        base_url = base_url or resolved_base
    base_url = (base_url or BASE).rstrip("/").removesuffix("/openai")
    fingerprint = hashlib.sha256((base_url + "\0" + (api_key or "")).encode()).hexdigest()
    with _lock:
        saved = _read(); key = str(_path()) + fingerprint
        same = saved.get("fp") == fingerprint
        if same and not refresh and _fresh(saved, TTL): return copy.deepcopy(saved["models"])
        if api_key and (refresh or time.monotonic() - _failures.get(key, -1e9) > 30):
            try:
                clean = _normalize((fetcher or _fetch)(api_key, base_url))
                if not clean: raise ValueError("Empty Google catalog")
                data = {"version": 1, "at": time.time(), "fp": fingerprint, "models": clean}
                path = _path()
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = path.with_suffix(".tmp")
                    temporary.write_text(json.dumps(data), encoding="utf-8")
                    atomic_replace(temporary, path)
                    stamp = path.stat().st_mtime_ns
                except OSError: stamp = -1
                _memory[str(path)] = (stamp, data); _failures.pop(key, None)
                return copy.deepcopy(clean)
            except Exception:
                _failures[key] = time.monotonic()
        return copy.deepcopy(saved["models"]) if same and _fresh(saved, STALE_TTL) else []


def cached_models() -> list[dict]:
    with _lock:
        saved = _read()
        return copy.deepcopy(saved["models"]) if _fresh(saved, STALE_TTL) else []


def metadata(model: str) -> dict | None:
    return next((r for r in cached_models() if r["id"] == model.removeprefix("models/")), None)
