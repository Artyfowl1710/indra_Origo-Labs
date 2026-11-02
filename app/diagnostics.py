"""Non-invasive diagnostics for the local workstation service stack."""
from __future__ import annotations
import asyncio, os, time
from urllib.parse import urlparse
import httpx
from .knowledge import configuration as knowledge_configuration
from .rag import get_rag_engine

def _display_url(value: str) -> str:
    """Redact credentials and query parameters from endpoint labels shown in the UI."""
    try:
        parsed = urlparse(value)
        host = parsed.hostname or "configured endpoint"
        if parsed.port:
            host += f":{parsed.port}"
        return f"{parsed.scheme}://{host}{parsed.path.rstrip('/')}"
    except (ValueError, TypeError):
        return "configured endpoint"


def _root(base: str) -> str:
    return (base or "").rstrip("/")

async def _probe(name: str, base: str, paths: tuple[str, ...], timeout: float = 1.5) -> dict:
    if not base:
        return {"name": name, "state": "not_configured", "url": None, "latency_ms": None, "detail": "No endpoint configured."}
    started = time.perf_counter()
    errors = []
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for path in paths:
            url = _root(base) + path
            try:
                response = await client.get(url)
                elapsed = round((time.perf_counter() - started) * 1000, 1)
                if response.status_code < 500:
                    detail = f"HTTP {response.status_code}"
                    if response.status_code == 401:
                        detail += " — reachable; authentication required"
                    return {"name": name, "state": "online" if response.status_code < 400 else "reachable", "url": _display_url(url), "latency_ms": elapsed, "detail": detail}
                errors.append(f"{path}: HTTP {response.status_code}")
            except (httpx.HTTPError, ValueError) as exc:
                errors.append(f"{path}: {type(exc).__name__}")
    elapsed = round((time.perf_counter() - started) * 1000, 1)
    host = _display_url(base)
    return {"name": name, "state": "offline", "url": _display_url(base), "latency_ms": elapsed, "detail": f"No health route answered at {host}. " + "; ".join(errors[-2:])}


async def _qdrant_inventory(base: str) -> dict:
    """Read collection metadata only; never issue vector queries or mutations."""
    try:
        headers = {}
        api_key = os.getenv("QDRANT_API_KEY", "").strip()
        if api_key:
            headers["api-key"] = api_key
        async with httpx.AsyncClient(timeout=1.5, follow_redirects=False) as client:
            response = await client.get(_root(base) + "/collections", headers=headers)
        if not response.is_success: return {"state": "unavailable", "detail": f"HTTP {response.status_code}"}
        payload = response.json(); rows = (payload.get("result") or {}).get("collections") or []
        return {"state": "online", "collection_count": len(rows), "collections": [str(x.get("name", "")) for x in rows[:30] if isinstance(x, dict)], "detail": "Read-only collection metadata."}
    except (httpx.HTTPError, ValueError) as exc:
        return {"state": "unavailable", "detail": type(exc).__name__}

async def _openapi_inventory(base: str) -> dict:
    """Summarize a local OpenAPI document without calling business endpoints."""
    try:
        async with httpx.AsyncClient(timeout=1.5, follow_redirects=False) as client:
            response = await client.get(_root(base) + "/openapi.json")
        if not response.is_success: return {"state": "not_exposed", "detail": f"HTTP {response.status_code}"}
        payload = response.json(); paths = payload.get("paths") or {}
        methods = sum(1 for value in paths.values() if isinstance(value, dict) for method in value if method.lower() in {"get", "post", "put", "patch", "delete"})
        return {"state": "online", "path_count": len(paths), "operation_count": methods, "paths": list(paths.keys())[:40], "detail": "OpenAPI metadata only; no operation was executed."}
    except (httpx.HTTPError, ValueError) as exc:
        return {"state": "not_exposed", "detail": type(exc).__name__}

async def diagnose(provider=None, workspace=None) -> dict:
    """Check configured local services without mutating state or sending prompts."""
    model_base = (provider.base_url if provider else os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8100/v1")).rstrip("/")
    specs = [
        _probe("model_gateway", model_base, ("/models",)),
        _probe("llama_swap", os.getenv("LLAMA_SWAP_URL", "http://127.0.0.1:8100"), ("/health", "/v1/models", "/")),
        _probe("llama_cpp_server", os.getenv("LLAMA_SERVER_URL", "http://127.0.0.1:5800"), ("/health", "/v1/models", "/")),
        _probe("qdrant", os.getenv("QDRANT_URL", "http://127.0.0.1:6333"), ("/healthz", "/readyz", "/")),
        _probe("workbench_api", os.getenv("WORKBENCH_API_URL", "http://127.0.0.1:8000"), ("/health", "/api/health", "/openapi.json", "/")),
    ]
    services = await asyncio.gather(*specs)
    model_ids = []
    gateway_state = next((s["state"] for s in services if s["name"] == "model_gateway"), "offline")
    if provider and gateway_state in {"online", "reachable"}:
        try: model_ids = await provider.list_models(force=True)
        except Exception: pass
    for service in services:
        if service["name"] == "model_gateway": service["models"] = model_ids[:30]
    qdrant_inventory, workbench_inventory = await asyncio.gather(
        _qdrant_inventory(os.getenv("QDRANT_URL", "http://127.0.0.1:6333")),
        _openapi_inventory(os.getenv("WORKBENCH_API_URL", "http://127.0.0.1:8000")),
    )
    # The application is useful even when optional services are offline.
    core_ok = True
    kb = knowledge_configuration()
    knowledge_status = {
        "enabled": bool(kb.get("enabled")),
        "collection": kb.get("collection") or None,
        "embedding_model": kb.get("embedding_model") or None,
        "embedding_endpoint": _display_url(str(kb.get("embedding_endpoint", ""))) if kb.get("embedding_endpoint") else None,
        "qdrant_endpoint": _display_url(str(kb.get("qdrant_endpoint", ""))) if kb.get("qdrant_endpoint") else None,
        "state": "configured" if kb.get("enabled") else "disabled",
        "read_only": True,
        "detail": "Legacy external Qdrant retrieval is available in read-only mode; live vector dimensions still need a query test." if kb.get("enabled") else "Legacy external Qdrant retrieval is disabled. First-party local SQLite/FTS5 retrieval is available in Knowledge Studio.",
    }
    local_rag = get_rag_engine().status()
    return {
        "checked_at": time.time(),
        "core": {"state": "online" if core_ok else "offline", "workspace": str(workspace) if workspace else None},
        "services": services,
        "integrations": {"qdrant": qdrant_inventory, "workbench_api": workbench_inventory, "knowledge_search": knowledge_status, "local_rag": local_rag},
        "summary": {"online": sum(s["state"] == "online" for s in services), "reachable": sum(s["state"] == "reachable" for s in services), "offline": sum(s["state"] == "offline" for s in services)},
        "notes": ["Service checks are read-only; no inference request is sent.", "Optional services may be offline without preventing the workstation UI from starting.", "Local RAG uses SQLite/FTS5; configured semantic embeddings transmit chunks to the configured embedding endpoint."],
    }
