"""Indra Origo local-first workstation API (Windows-oriented, loopback-only)."""
from __future__ import annotations
import asyncio, hashlib, hmac, json, os, re, secrets, shutil, tempfile, threading, time, uuid
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlsplit
from typing import Literal
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", encoding="utf-8-sig")
from fastapi import FastAPI, HTTPException, Query, Request  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from .agent import Agent  # noqa: E402
from . import extensions, web_tools, sandbox, git_tools, amplifier, scout, hmi, evidence  # noqa: E402
from .permissions import PermissionBroker  # noqa: E402
from .diagnostics import diagnose  # noqa: E402
from .providers import OpenAICompatibleProvider, safe_endpoint_label  # noqa: E402
from .attachments import AttachmentError, prepare_chat_attachments  # noqa: E402
from .modalities import capability_snapshot  # noqa: E402
from .knowledge import configuration as knowledge_configuration  # noqa: E402
from .rag import get_rag_engine, MAX_INGEST_BYTES  # noqa: E402
from .store import Store  # noqa: E402
from .tools import build_context_pack, ensure_workspace, is_readable_text_file, is_sensitive_path, safe_path, search_files, set_workspace, workspace_inventory  # noqa: E402

@asynccontextmanager
async def lifespan(_app):
    try:
        yield
    finally:
        # Keep provider clients/connection pools from leaking across server shutdowns.
        await provider.aclose()


app = FastAPI(title="Indra Origo", version="1.7.2", docs_url="/api/docs", redoc_url=None, lifespan=lifespan)
store = Store()
rag_engine = get_rag_engine(store.root)
capsule_service = evidence.CapsuleService(store.root)
proof_ledger = evidence.ProofLedger(store)
provider = OpenAICompatibleProvider()
agent = Agent(provider, store)
permission_broker = PermissionBroker(str(store.get_setting("network_policy") or os.getenv("INDRA_AGENT_NETWORK_POLICY", "ask")))
saved_docker_sandbox = store.get_setting("docker_sandbox_enabled")
if isinstance(saved_docker_sandbox, bool):
    sandbox.set_runtime_enabled(saved_docker_sandbox)
saved_sandbox_image = store.get_setting("sandbox_image")
if isinstance(saved_sandbox_image, str) and saved_sandbox_image.strip():
    try:
        sandbox.set_image_override(saved_sandbox_image)
    except ValueError:
        store.event("sandbox_image_setting_ignored", reason="invalid_image_reference")
STATIC = Path(__file__).parent / "static"
try:
    MAX_CONCURRENT_RUNS = max(1, min(8, int(os.getenv("INDRA_MAX_CONCURRENT_RUNS", "2"))))
except ValueError:
    MAX_CONCURRENT_RUNS = 2

class RunSlots:
    """Cross-thread run admission control, with exactly-once release tokens."""
    def __init__(self, capacity: int):
        self.capacity, self.active, self.lock = capacity, 0, threading.Lock()
    def acquire(self) -> bool:
        with self.lock:
            if self.active >= self.capacity: return False
            self.active += 1
            return True
    def release(self) -> None:
        with self.lock: self.active = max(0, self.active - 1)
    def snapshot(self) -> dict:
        with self.lock: return {"active": self.active, "capacity": self.capacity}
run_slots = RunSlots(MAX_CONCURRENT_RUNS)

REMOTE_COOKIE_NAME = "origo_remote_session"
REMOTE_SESSION_TTL_SECONDS = 12 * 60 * 60

def _remote_enabled() -> bool:
    return os.getenv("INDRA_REMOTE_ACCESS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}

def _remote_token() -> str:
    return os.getenv("INDRA_REMOTE_ACCESS_TOKEN", "").strip()

def _remote_cookie(token: str, hostname: str, issued_at: int | None = None) -> str:
    issued = int(time.time()) if issued_at is None else int(issued_at)
    nonce = secrets.token_hex(16)
    payload = f"origo-remote-v1\n{hostname.lower()}\n{issued}\n{nonce}".encode("utf-8")
    signature = hmac.new(token.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"{issued}.{nonce}.{signature}"

def _valid_remote_cookie(value: str | None, token: str, hostname: str, now: int | None = None) -> bool:
    if not value or len(token) < 32:
        return False
    try:
        issued_raw, nonce, signature = value.split(".", 2)
        issued = int(issued_raw)
    except (ValueError, TypeError):
        return False
    current = int(time.time()) if now is None else int(now)
    if current < issued or current - issued > REMOTE_SESSION_TTL_SECONDS:
        return False
    if not re.fullmatch(r"[a-f0-9]{32}", nonce) or not re.fullmatch(r"[a-f0-9]{64}", signature):
        return False
    payload = f"origo-remote-v1\n{hostname.lower()}\n{issued}\n{nonce}".encode("utf-8")
    expected = hmac.new(token.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return secrets.compare_digest(signature, expected)

REMOTE_LOGIN_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="referrer" content="no-referrer"><title>Origo Remote sign in</title><style>body{margin:0;background:#0b1015;color:#eef5f6;font:16px system-ui,sans-serif;display:grid;min-height:100vh;place-items:center}.card{width:min(90vw,420px);padding:28px;border:1px solid #2b3a42;border-radius:20px;background:#111a20;box-sizing:border-box}h1{font-size:24px;margin:0 0 8px;color:#76f7c4}p{line-height:1.5;color:#b1bfc8}label{display:block;margin:22px 0 8px}input{box-sizing:border-box;width:100%;padding:14px;background:#19222a;border:1px solid #40515c;border-radius:10px;color:white;font:inherit}button{width:100%;margin-top:12px;padding:14px;border:0;border-radius:10px;background:#76f7c4;color:#092019;font-weight:700;font:inherit}small{display:block;margin-top:18px;color:#8da0aa}</style></head><body><main class="card"><h1>INDRA ORIGO</h1><h2>Sign in to your workstation</h2><p>Enter the remote-access token shown by the setup script on your PC. Keep it private. Sessions expire after 12 hours.</p><form method="post" action="/remote/login"><label for="token">Remote access token</label><input id="token" name="token" type="password" autocomplete="current-password" required maxlength="256"><button type="submit">Unlock workstation</button></form><small>Private network access is still required. Never share this token.</small></main></body></html>"""

class LocalSafetyMiddleware:
    """Defence in depth against DNS-rebinding/local browser calls; not authentication."""
    def __init__(self, asgi_app): self.app = asgi_app
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send); return
        from starlette.requests import Request as StarletteRequest
        req = StarletteRequest(scope, receive=receive)
        host_header = req.headers.get("host", "")
        try: hostname = (urlsplit("//" + host_header).hostname or "").lower()
        except ValueError: hostname = ""
        # TestClient has a synthetic source address ('testclient'). Never allow its
        # synthetic Host header for an ordinary network client; Host is attacker-controlled.
        loopback_hosts = {"127.0.0.1", "localhost", "::1"}
        client = scope.get("client") or (None, None)
        if hostname == "testserver" and client[0] == "testclient":
            loopback_hosts.add("testserver")
        remote_enabled = _remote_enabled()
        trusted_tailnet_host = remote_enabled and hostname.endswith(".ts.net") and not hostname.startswith(".")

        async def secure_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                if trusted_tailnet_host:
                    # Override endpoint-specific cache hints: no remote response should
                    # retain private workspace, chat, or diagnostic data in a browser cache.
                    headers = [(name, value) for name, value in headers if name.lower() != b"cache-control"]
                present = {name.lower() for name, _ in headers}
                additions = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"permissions-policy", b"camera=(), microphone=(self), geolocation=()"),
                    (b"content-security-policy", b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; frame-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"),
                ]
                # Remote API responses can contain private workspace data; never allow
                # browser/proxy caches to persist them. HSTS is host-only (no includeSubDomains
                # because ts.net is shared infrastructure).
                if trusted_tailnet_host:
                    additions.extend([
                        (b"cache-control", b"no-store"),
                        (b"strict-transport-security", b"max-age=31536000"),
                    ])
                for name, value in additions:
                    if name not in present:
                        headers.append((name, value))
                        present.add(name)
                message["headers"] = headers
            await send(message)

        if hostname not in loopback_hosts and not trusted_tailnet_host:
            response = JSONResponse({"detail": "Indra Origo only accepts loopback connections unless private Tailscale access is explicitly enabled."}, status_code=421)
            await response(scope, receive, secure_send); return
        origin = req.headers.get("origin")
        if origin:
            try:
                parts = urlsplit(origin)
                if origin == "null" or parts.scheme not in {"http", "https"} or parts.netloc.lower() != host_header.lower():
                    response = JSONResponse({"detail": "Cross-origin requests are blocked by local safety policy."}, status_code=403)
                    await response(scope, receive, secure_send); return
            except ValueError:
                response = JSONResponse({"detail": "Invalid Origin header."}, status_code=403)
                await response(scope, receive, secure_send); return
        if req.headers.get("sec-fetch-site", "").lower() == "cross-site":
            response = JSONResponse({"detail": "Cross-site requests are blocked by local safety policy."}, status_code=403)
            await response(scope, receive, secure_send); return
        # Remote mode is a separate trust boundary: tailnet membership alone is not
        # sufficient. Require a configured high-entropy token and a short-lived signed cookie.
        if trusted_tailnet_host:
            path = scope.get("path", "/")
            method = scope.get("method", "GET").upper()
            token = _remote_token()
            if path != "/remote/login" and len(token) < 32:
                response = JSONResponse({"detail": "Remote access is not configured safely. Set a random INDRA_REMOTE_ACCESS_TOKEN of at least 32 characters on the PC."}, status_code=503)
                await response(scope, receive, secure_send); return
            cookie = req.cookies.get(REMOTE_COOKIE_NAME)
            authenticated = _valid_remote_cookie(cookie, token, hostname)
            if path == "/remote/login":
                if method not in {"GET", "POST"}:
                    response = JSONResponse({"detail": "Method not allowed."}, status_code=405)
                    await response(scope, receive, secure_send); return
                if method == "GET" and authenticated:
                    response = RedirectResponse(url="/", status_code=303, headers={"Cache-Control": "no-store"})
                    await response(scope, receive, secure_send); return
            elif not authenticated:
                if path == "/" and method == "GET":
                    response = RedirectResponse(url="/remote/login", status_code=303, headers={"Cache-Control": "no-store"})
                else:
                    response = JSONResponse({"detail": "Remote sign-in required. Open the workstation page and enter your remote-access token."}, status_code=401, headers={"Cache-Control": "no-store"})
                await response(scope, receive, secure_send); return
        await self.app(scope, receive, secure_send)
app.add_middleware(LocalSafetyMiddleware)

# Restore persisted selections after .env defaults are loaded.
saved_workspace = store.get_setting("workspace")
if isinstance(saved_workspace, str) and saved_workspace:
    try: set_workspace(saved_workspace)
    except (OSError, ValueError): store.event("workspace_restore_skipped", reason="saved_path_unavailable")
saved_profile = store.get_setting("provider_profile", "local")
if saved_profile in {"local", "hosted"} and saved_profile != provider.profile:
    try:
        provider.use_profile(saved_profile)
    except Exception as exc:
        store.event("provider_profile_restore_skipped", requested_profile=saved_profile, reason=type(exc).__name__)
        store.set_setting("provider_profile", "local")
saved_model = store.get_setting("model")
saved_model_profile = store.get_setting("model_profile")
if isinstance(saved_model, str) and saved_model.strip() and (saved_model_profile == provider.profile or (saved_model_profile is None and provider.profile == "local")):
    provider.model = saved_model.strip(); provider._resolved_model = None

class PlanValidationRequest(BaseModel):
    plan: dict | str
class ContextPackRequest(BaseModel):
    items: list[dict] = Field(default_factory=list, max_length=500)
    token_budget: int = Field(default=4096, ge=1, le=100000)
class VerifyStepRequest(BaseModel):
    verifier: Literal["nonempty", "json", "tests", "numeric", "manual"]
    result: object = None
    expected: object = None
class ArithmeticVerifyRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=200)
    claimed: float
    tolerance: float = Field(default=1e-9, ge=0, le=1e-3)
class TokenEstimateRequest(BaseModel):
    text: str = Field(default="", max_length=200000)
class CapabilityProfileRequest(BaseModel):
    results: dict = Field(default_factory=dict)


class RAGIngestRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=240)
    mime_type: str = Field(default="text/plain", max_length=120)
    content_base64: str = Field(min_length=1, max_length=9_800_000)
    tags: list[str] = Field(default_factory=list, max_length=20)
class RAGSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1200)
    limit: int = Field(default=8, ge=1, le=12)
    include_context: bool = True
class RAGWorkspaceIndexRequest(BaseModel):
    max_files: int = Field(default=60, ge=1, le=100)
    max_total_bytes: int = Field(default=12_000_000, ge=100_000, le=20_000_000)

class ChatAttachment(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    mime_type: str = Field(default="application/octet-stream", max_length=120)
    kind: Literal["text", "image", "pdf"]
    text_content: str = Field(default="", max_length=24000)
    data_base64: str = Field(default="", max_length=7000000)

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    attachments: list[ChatAttachment] = Field(default_factory=list, max_length=4)
    mode: Literal["plan", "build"] = "build"
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)
    conversation_id: str | None = Field(default=None, max_length=32)
    context: str | None = Field(default=None, max_length=12000)
    skills: list[str] = Field(default_factory=list, max_length=6)
class Decision(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
class WorkspaceSelection(BaseModel):
    path: str = Field(min_length=1, max_length=2048)
class ModelSelection(BaseModel):
    model: str = Field(min_length=1, max_length=300)
class ProviderProfileSelection(BaseModel):
    profile: Literal["local", "hosted"]
class ScratchpadUpdate(BaseModel):
    content: str = Field(default="", max_length=30000)
class CapsuleCreateRequest(BaseModel):
    run_id: str | None = Field(default=None, max_length=64)
    workspace_paths: list[str] = Field(default_factory=list, max_length=250)
    include_recent_event_metadata: bool = True
class ProofEvidenceRequest(BaseModel):
    path: str = Field(min_length=1, max_length=2048)
    excerpt: str = Field(min_length=1, max_length=3000)
    note: str = Field(default="", max_length=500)
class ProofClaimRequest(BaseModel):
    statement: str = Field(min_length=1, max_length=3000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
class ProofLintRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100000)
    claim_ids: list[str] | None = Field(default=None, max_length=1000)
class ProofClaimReviewRequest(BaseModel):
    reviewed: bool
class WebSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=8)
class WebFetchRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    max_chars: int = Field(default=12000, ge=500, le=18000)
class WebResearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    max_pages: int = Field(default=3, ge=1, le=4)
    max_chars: int = Field(default=9000, ge=2000, le=16000)
class WebCrawlRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    max_pages: int = Field(default=4, ge=1, le=5)
    max_chars: int = Field(default=10000, ge=2000, le=16000)
class SandboxRunRequest(BaseModel):
    command: list[str] = Field(min_length=1, max_length=24)
    cwd: str = Field(default=".", max_length=2048)
    timeout_seconds: int = Field(default=30, ge=1, le=45)
    network_access: bool = False
class TaskGraphNode(BaseModel):
    id: str = Field(min_length=1, max_length=24, pattern=r"^[A-Za-z0-9_-]+$")
    task: str = Field(min_length=1, max_length=1500)
    depends_on: list[str] = Field(default_factory=list, max_length=5)
class TaskGraphRequest(BaseModel):
    tasks: list[TaskGraphNode] = Field(min_length=1, max_length=6)
    max_concurrency: int = Field(default=2, ge=1, le=3)
    context: str | None = Field(default=None, max_length=6000)
    skills: list[str] = Field(default_factory=list, max_length=6)
class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", max_length=120)
class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=120)
class RunFeedbackRequest(BaseModel):
    run_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    conversation_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    rating: Literal["useful", "incorrect", "incomplete", "risky"]
class PolicyUpdate(BaseModel):
    network_policy: Literal["ask", "deny"] | None = None
    docker_sandbox_enabled: bool | None = None
    clear_session_grants: bool = False
    reset_sandbox_image: bool = False
class PermissionDecision(BaseModel):
    decision: Literal["approve", "deny"]
    scope: Literal["once", "domain"] = "once"
class SandboxPullRequest(BaseModel):
    confirmed: bool

class SandboxBuildRequest(BaseModel):
    confirmed: bool

class SandboxProposeRequest(BaseModel):
    sandbox_run_id: str = Field(pattern=r"^[a-f0-9]{12}$")
    paths: list[str] = Field(min_length=1, max_length=20)


class ConversationRunLocks:
    """Prevent two turns from interleaving inside one saved conversation."""
    def __init__(self):
        self.active: set[str] = set()
        self.lock = threading.Lock()
    def acquire(self, conversation_id: str) -> bool:
        with self.lock:
            if conversation_id in self.active:
                return False
            self.active.add(conversation_id)
            return True
    def release(self, conversation_id: str) -> None:
        with self.lock:
            self.active.discard(conversation_id)
    def contains(self, conversation_id: str) -> bool:
        with self.lock:
            return conversation_id in self.active

conversation_run_locks = ConversationRunLocks()

def _check_history(req: ChatRequest) -> None:
    if len(set(req.skills)) != len(req.skills) or any(not re.fullmatch(r"[a-z0-9_-]{1,100}", skill) for skill in req.skills):
        raise HTTPException(422, "Skills must be unique installed skill IDs using letters, numbers, underscores, or hyphens.")
    total = 0
    for item in req.history:
        role, content = item.get("role"), item.get("content")
        if role not in {"user", "assistant"}: raise HTTPException(422, "History may contain only user and assistant messages.")
        if len(content or "") > 6000: raise HTTPException(422, "Each history message must be at most 6,000 characters.")
        total += len(content or "")
    if total > 24000: raise HTTPException(422, "Conversation history exceeds 24,000 characters. Start a new conversation.")

def _start_conversation_turn(req: ChatRequest) -> str | None:
    if not req.message.strip():
        raise HTTPException(422, "Message must contain non-whitespace text.")
    _check_history(req)
    conversation_id = req.conversation_id
    if not conversation_id:
        return None
    if not re.fullmatch(r"[0-9a-f]{32}", conversation_id):
        raise HTTPException(422, "Invalid conversation ID.")
    conversation = store.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversation not found. Refresh the recent chats list.")
    current_workspace = str(ensure_workspace().resolve())
    saved_workspace = str(conversation.get("workspace") or "")
    try:
        if not saved_workspace or str(Path(saved_workspace).resolve(strict=True)) != current_workspace:
            raise HTTPException(409, "This conversation belongs to a different workspace. Switch to its saved workspace in Files & context before continuing.")
    except OSError:
        raise HTTPException(409, "This conversation's saved workspace is unavailable. Choose an existing workspace in Files & context.")
    if not conversation_run_locks.acquire(conversation_id):
        raise HTTPException(409, "A turn is already running in this conversation. Wait for it to finish or cancel it.")
    try:
        if not store.append_conversation_message(conversation_id, "user", req.message):
            raise HTTPException(404, "Conversation no longer exists.")
    except Exception:
        conversation_run_locks.release(conversation_id)
        raise
    return conversation_id


def _finish_conversation_turn(conversation_id: str | None, run: dict) -> None:
    if not conversation_id:
        return
    self_contained_answer = str(run.get("answer") or "The run completed without a text answer.")
    store.append_conversation_message(
        conversation_id, "assistant", self_contained_answer,
        run_id=str(run.get("run_id") or ""), status=str(run.get("status") or "unknown"),
    )


def _release_run(conversation_id: str | None) -> None:
    run_slots.release()
    if conversation_id:
        conversation_run_locks.release(conversation_id)


def _backup_root() -> Path:
    raw = Path(os.getenv("INDRA_BACKUP_DIR", str(PROJECT_ROOT / "data" / "backups"))).expanduser()
    return (raw if raw.is_absolute() else PROJECT_ROOT / raw).resolve()

def _sha256_file(path: Path) -> str | None:
    if not path.exists(): return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""): h.update(chunk)
    return h.hexdigest()

def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); temp_name = None
    try:
        with tempfile.NamedTemporaryFile("wb", prefix=".indra-", suffix=".tmp", dir=str(path.parent), delete=False) as tmp:
            temp_name = tmp.name; tmp.write(content); tmp.flush(); os.fsync(tmp.fileno())
        os.replace(temp_name, path); temp_name = None
    finally:
        if temp_name:
            try: Path(temp_name).unlink(missing_ok=True)
            except OSError: pass

@app.get("/")
def index(): return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

@app.get("/remote/login", response_class=HTMLResponse)
def remote_login_page():
    if not _remote_enabled():
        raise HTTPException(404, "Remote access is disabled.")
    if len(_remote_token()) < 32:
        return HTMLResponse("<h1>Remote sign-in unavailable</h1><p>Configure a random INDRA_REMOTE_ACCESS_TOKEN of at least 32 characters, then restart Origo.</p>", status_code=503, headers={"Cache-Control": "no-store"})
    return HTMLResponse(REMOTE_LOGIN_HTML, headers={"Cache-Control": "no-store"})

@app.post("/remote/login")
async def remote_login_submit(request: Request):
    if not _remote_enabled():
        raise HTTPException(404, "Remote access is disabled.")
    token = _remote_token()
    if len(token) < 32:
        raise HTTPException(503, "Remote access token is not configured safely.")
    content_length = request.headers.get("content-length", "").strip()
    if content_length.isdigit() and int(content_length) > 4096:
        raise HTTPException(413, "Login request is too large.")
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 4096:
            raise HTTPException(413, "Login request is too large.")
        raw.extend(chunk)
    try:
        form = parse_qs(raw.decode("utf-8", errors="strict"), keep_blank_values=True, max_num_fields=8)
    except (UnicodeDecodeError, ValueError):
        form = {}
    supplied = form.get("token", [""])[0]
    if not secrets.compare_digest(supplied.encode("utf-8"), token.encode("utf-8")):
        return HTMLResponse(REMOTE_LOGIN_HTML.replace("Enter the remote-access token shown by the setup script on your PC.", "The token was not accepted. Try again.", 1), status_code=401, headers={"Cache-Control": "no-store"})
    hostname = (urlsplit("//" + request.headers.get("host", "")).hostname or "").lower()
    if not hostname.endswith(".ts.net"):
        raise HTTPException(403, "Sign-in is available only through the private Tailscale HTTPS endpoint.")
    response = RedirectResponse(url="/", status_code=303, headers={"Cache-Control": "no-store"})
    response.set_cookie(REMOTE_COOKIE_NAME, _remote_cookie(token, hostname), max_age=REMOTE_SESSION_TTL_SECONDS, httponly=True, secure=True, samesite="strict", path="/")
    return response

@app.get("/remote/logout")
def remote_logout():
    if not _remote_enabled():
        raise HTTPException(404, "Remote access is disabled.")
    response = RedirectResponse(url="/remote/login", status_code=303, headers={"Cache-Control": "no-store"})
    response.delete_cookie(REMOTE_COOKIE_NAME, path="/", secure=True, httponly=True, samesite="strict")
    return response

@app.get("/api/status")
def status():
    return {"app": "Indra Origo", "version": app.version, "model": provider.model,
            "resolved_model": provider._resolved_model, "base_url": provider.display_endpoint,
            "workspace": str(ensure_workspace()), "run_capacity": run_slots.snapshot(),
            "safety": {"workspace_scoped": True, "writes_require_approval": True,
                       "secret_files_blocked": True, "symlinks_blocked": True,
            "shell_enabled": False, "desktop_control": False, "host": "127.0.0.1",
                       "network_policy": permission_broker.network_policy,
                       "docker_sandbox_enabled": sandbox.is_enabled()}}

@app.get("/api/health")
def health(): return {"ok": True, "app": "Indra Origo", "version": app.version}

@app.get("/api/capabilities")
def capabilities():
    return capability_snapshot(provider)

@app.get("/api/providers")
def provider_profiles():
    return provider.profile_info()

@app.post("/api/provider/profile")
def select_provider_profile(req: ProviderProfileSelection):
    try:
        provider.use_profile(req.profile)
    except Exception as exc:
        raise HTTPException(409, str(exc)) from exc
    store.set_setting("provider_profile", req.profile)
    store.set_setting("model", provider.model)
    store.set_setting("model_profile", provider.profile)
    store.event("provider_profile_changed", profile=provider.profile, endpoint=provider.display_endpoint)
    return {"active": provider.profile, "model": provider.model, "endpoint": provider.display_endpoint,
            "profiles": provider.profile_info()["profiles"], "api_key_exposed": False}

@app.get("/api/scratchpad")
def get_scratchpad():
    content = store.get_setting("scratchpad_content", "")
    return {"content": content if isinstance(content, str) else "", "max_chars": 30000,
            "purpose": "Inspectable project notes only; not hidden chain-of-thought.", "persistent": True}

@app.put("/api/scratchpad")
def update_scratchpad(req: ScratchpadUpdate):
    content = req.content
    store.set_setting("scratchpad_content", content)
    store.event("scratchpad_updated", chars=len(content))
    return {"saved": True, "chars": len(content), "max_chars": 30000}

@app.get("/api/sessions")
def list_sessions():
    return store.list_conversations(60)

@app.post("/api/sessions")
def create_session(req: ConversationCreate):
    row = store.create_conversation(str(ensure_workspace()), req.title)
    return row

@app.get("/api/sessions/{conversation_id}")
def get_session(conversation_id: str):
    if not re.fullmatch(r"[0-9a-f]{32}", conversation_id):
        raise HTTPException(422, "Invalid conversation ID.")
    row = store.get_conversation(conversation_id)
    if not row:
        raise HTTPException(404, "Conversation not found")
    return row

@app.patch("/api/sessions/{conversation_id}")
def rename_session(conversation_id: str, req: ConversationRename):
    if not re.fullmatch(r"[0-9a-f]{32}", conversation_id):
        raise HTTPException(422, "Invalid conversation ID.")
    try:
        row = store.rename_conversation(conversation_id, req.title)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if not row:
        raise HTTPException(404, "Conversation not found")
    return {key: row[key] for key in ("conversation_id", "title", "workspace", "created_at", "updated_at")}

@app.delete("/api/sessions/{conversation_id}")
def delete_session(conversation_id: str):
    if not re.fullmatch(r"[0-9a-f]{32}", conversation_id):
        raise HTTPException(422, "Invalid conversation ID.")
    if conversation_run_locks.contains(conversation_id):
        raise HTTPException(409, "Cannot delete a conversation while a run is active.")
    if not store.delete_conversation(conversation_id):
        raise HTTPException(404, "Conversation not found")
    return {"deleted": True, "conversation_id": conversation_id}

@app.get("/api/export")
def export_data():
    """Download a local research/debug bundle; traces can include project snippets and prompts."""
    actions_for_export = []
    for action in store.list_actions()[:500]:
        actions_for_export.append({key: value for key, value in action.items() if key != "content"})
    bundle = {
        "product": "Indra Origo", "version": app.version,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workspace": str(ensure_workspace()), "model_endpoint": provider.display_endpoint,
        "settings": settings(), "metrics": metrics(), "runs": store.list_runs()[:100],
        "conversations": [row for summary in store.list_conversations(60)
                          if (row := store.get_conversation(summary["conversation_id"])) is not None],
        "actions": actions_for_export, "events": store.list_events(250),
        "notice": "Local research/debug export. Run traces and saved conversations may contain user prompts, tool arguments, and project excerpts. Review before sharing.",
    }
    return JSONResponse(bundle, headers={"Content-Disposition": 'attachment; filename="indra-lok-research-bundle.json"'})

@app.get("/api/settings")
def settings():
    return {"workspace": str(ensure_workspace()), "model": provider.model,
            "model_endpoint": provider.display_endpoint, "profile": os.getenv("INDRA_PROFILE", "auto"),
            "max_concurrent_runs": MAX_CONCURRENT_RUNS,
            "permissions": {**permission_broker.snapshot(), "docker_sandbox_enabled": sandbox.is_enabled(),
                            "docker_sandbox": sandbox.status()},
            "features": {"streaming": True, "browser_voice_input": True, "browser_voice_output": True,
                          "chat_attachments": True, "pdf_text_extraction": True, "image_forwarding_opt_in": True,
                          "approval_gated_writes": True, "secret_filtering": True,
                          "sqlite_persistence": True, "persistent_conversations": True, "research_export": True,
                          "workspace_search": True, "model_smoke_test": True,
                          "local_hybrid_rag": True, "local_rag_semantic": rag_engine.status()["semantic_search_active"],
                          "qdrant_read_only_retrieval": bool(knowledge_configuration().get("enabled")),
            "shell_tool": False, "desktop_control": False}}

@app.get("/api/policy")
def get_policy():
    return {**permission_broker.snapshot(), "docker_sandbox_enabled": sandbox.is_enabled(),
            "docker_sandbox": sandbox.status(),
            "defaults": {"network": "Ask for every agent-initiated web action", "writes": "Always require a separate file-change approval", "sandbox": "Off until explicitly enabled"}}

@app.post("/api/policy")
def update_policy(req: PolicyUpdate):
    changed = {}
    if req.network_policy is not None:
        permission_broker.set_network_policy(req.network_policy)
        store.set_setting("network_policy", req.network_policy)
        store.event("network_policy_changed", policy=req.network_policy)
        changed["network_policy"] = req.network_policy
    if req.docker_sandbox_enabled is not None:
        sandbox.set_runtime_enabled(req.docker_sandbox_enabled)
        store.set_setting("docker_sandbox_enabled", req.docker_sandbox_enabled)
        store.event("docker_sandbox_setting_changed", enabled=req.docker_sandbox_enabled)
        changed["docker_sandbox_enabled"] = req.docker_sandbox_enabled
    if req.clear_session_grants:
        permission_broker.clear_session_grants()
        store.event("permission_session_grants_cleared")
        changed["session_grants_cleared"] = True
    if req.reset_sandbox_image:
        sandbox.set_image_override(None)
        store.set_setting("sandbox_image", None)
        store.event("sandbox_image_override_reset")
        changed["sandbox_image_reset"] = True
    return {"status": "updated", "changed": changed, **get_policy()}

@app.get("/api/permissions/pending")
def pending_permissions():
    rows = permission_broker.pending()
    return {"pending": rows, "count": len(rows)}

@app.post("/api/permissions/{permission_id}")
async def decide_permission(permission_id: str, req: PermissionDecision):
    try:
        decision = permission_broker.decide(permission_id, req.decision, req.scope)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    store.event("permission_decided", permission_id=permission_id, decision=decision["decision"],
                scope=decision["scope"], kind=decision["kind"], tool=decision["tool"], host=decision.get("host"))
    return {"status": "decided", **decision}

@app.post("/api/sandbox/build-image")
async def sandbox_build_dev_image(req: SandboxBuildRequest):
    """Build the reviewed local dev image after an explicit host-side network confirmation."""
    if req.confirmed is not True:
        raise HTTPException(400, "Explicit confirmation is required before building a Docker image and downloading packages.")
    if not run_slots.acquire():
        raise HTTPException(429, "Another workload is running. Wait before building the sandbox image.")
    try:
        store.event("sandbox_image_build_requested", confirmed=True, context="docker/ only")
        result = await asyncio.to_thread(sandbox.build_dev_image_after_explicit_confirmation, req.confirmed)
        if result.get("status") == "built":
            sandbox.set_image_override(result["image"])
            store.set_setting("sandbox_image", result["image"])
            store.event("sandbox_image_build_finished", status="built", image=result["image"], context="docker/ only")
        else:
            store.event("sandbox_image_build_finished", status="failed")
        return result
    finally:
        run_slots.release()


@app.post("/api/sandbox/pull-image")
async def sandbox_pull_image(req: SandboxPullRequest):
    if not req.confirmed:
        raise HTTPException(400, "Explicit confirmation is required before contacting the container registry.")
    if not run_slots.acquire():
        raise HTTPException(429, "Another workload is running. Wait before pulling a sandbox image.")
    try:
        store.event("sandbox_image_pull_requested", confirmed=True)
        result = await asyncio.to_thread(sandbox.pull_image_after_explicit_confirmation, req.confirmed)
        if "error" in result:
            store.event("sandbox_image_pull_finished", status="failed")
            raise HTTPException(400, result["error"])
        store.event("sandbox_image_pull_finished", status="pulled", image=result.get("image"))
        return result
    finally:
        run_slots.release()

@app.post("/api/workspace/select")
def select_workspace(req: WorkspaceSelection):
    try: selected = set_workspace(req.path)
    except (OSError, RuntimeError, ValueError) as exc: raise HTTPException(400, f"Workspace was not changed: {str(exc)[:200]}")
    store.set_setting("workspace", str(selected)); store.event("workspace_selected", path=str(selected))
    return {"workspace": str(selected), "files": len(workspace_inventory(500))}

@app.get("/api/doctor")
async def doctor(): return await diagnose(provider, ensure_workspace())

@app.get("/api/models")
async def models():
    try:
        ids = await provider.list_models(force=True)
        return {"configured": provider.model, "resolved": provider._resolved_model, "models": ids[:100], "endpoint": provider.display_endpoint}
    except Exception as exc:
        return {"configured": provider.model, "resolved": provider._resolved_model, "models": [],
                "endpoint": provider.display_endpoint, "error": str(exc)[:350]}

@app.post("/api/model")
async def select_model(req: ModelSelection):
    model = req.model.strip()
    if not model: raise HTTPException(400, "Model name cannot be empty.")
    try: ids = await provider.list_models(force=True)
    except Exception as exc: raise HTTPException(503, f"Model gateway unavailable ({type(exc).__name__}). Start it and retry.")
    if model != "auto" and model not in ids: raise HTTPException(400, "That model ID is not advertised by the configured gateway.")
    provider.model = model; provider._resolved_model = None if model == "auto" else model; provider._models_checked_at = 0.0
    store.set_setting("model", model); store.event("model_selected", model=model)
    return {"model": model, "resolved_model": provider._resolved_model}

@app.post("/api/model/smoke")
async def model_smoke():
    """Run a user-triggered, bounded inference + non-executing tool-call probe."""
    if not run_slots.acquire():
        raise HTTPException(429, "All inference slots are busy. Wait for a run to finish before testing the model.")
    started = time.perf_counter()
    tool = [{"type": "function", "function": {
        "name": "indra_harness_probe",
        "description": "A harmless capability-test function. It has no side effects and must not be executed.",
        "parameters": {"type": "object", "properties": {"status": {"type": "string", "enum": ["ok"]}},
                        "required": ["status"], "additionalProperties": False},
    }}]
    try:
        try:
            timeout = max(5.0, min(float(os.getenv("INDRA_SMOKE_TIMEOUT", "45")), 120.0))
        except (TypeError, ValueError):
            timeout = 45.0
        message = await asyncio.wait_for(provider.chat([
            {"role": "system", "content": "You are testing a model endpoint. No real tools are available. This synthetic probe is safe and has no side effects."},
            {"role": "user", "content": "If you support function calling, call indra_harness_probe exactly once with {\"status\":\"ok\"}. Do not invent other tool calls. If function calling is unavailable, reply briefly in text."},
        ], tools=tool, max_tokens=64), timeout=timeout)
        calls = message.get("tool_calls") if isinstance(message, dict) else []
        calls = calls if isinstance(calls, list) else []
        detected = any(isinstance(call, dict) and isinstance(call.get("function"), dict)
                       and call["function"].get("name") == "indra_harness_probe" for call in calls)
        content = message.get("content") if isinstance(message, dict) else ""
        text_ok = bool((isinstance(content, str) and content.strip()) or detected)
        outcome = "passed" if detected else "partial" if text_ok else "failed"
        duration = round((time.perf_counter() - started) * 1000, 1)
        resolved = provider._resolved_model or provider.model
        store.event("model_smoke_test", status=outcome, duration_ms=duration,
                    model=resolved, tool_calling_detected=detected, text_generation_ok=text_ok)
        return {"status": outcome, "text_generation_ok": text_ok,
                "tool_calling_detected": detected, "model": resolved,
                "endpoint": provider.display_endpoint, "duration_ms": duration,
                "summary": ("Text generation and the synthetic tool-call response both worked. No tool was executed." if detected
                            else "Text generation responded, but the expected tool call was not observed. Tool calling is not verified for this model/template." if text_ok
                            else "The endpoint returned no usable assistant output.")}
    except asyncio.TimeoutError:
        duration = round((time.perf_counter() - started) * 1000, 1)
        store.event("model_smoke_test", status="timeout", duration_ms=duration, model=provider._resolved_model or provider.model)
        return {"status": "timeout", "text_generation_ok": False, "tool_calling_detected": False,
                "model": provider._resolved_model or provider.model, "endpoint": provider.display_endpoint,
                "duration_ms": duration, "summary": f"Model smoke test exceeded {timeout:g} seconds. Check model loading and server logs."}
    except Exception as exc:
        duration = round((time.perf_counter() - started) * 1000, 1)
        store.event("model_smoke_test", status="failed", duration_ms=duration,
                    model=provider._resolved_model or provider.model, error_type=type(exc).__name__)
        return {"status": "unreachable", "text_generation_ok": False, "tool_calling_detected": False,
                "model": provider._resolved_model or provider.model, "endpoint": provider.display_endpoint,
                "duration_ms": duration, "summary": f"Inference request failed ({type(exc).__name__}). Start the model server and check Diagnostics."}
    finally:
        run_slots.release()

@app.get("/api/rag/status")
def rag_status():
    return rag_engine.status()

@app.get("/api/rag/documents")
def rag_documents(limit: int = Query(default=200, ge=1, le=500)):
    return {"documents": rag_engine.list_documents(limit), "status": rag_engine.status()}

@app.post("/api/rag/ingest")
def rag_ingest(req: RAGIngestRequest):
    try:
        result = rag_engine.ingest_base64(req.filename, req.mime_type, req.content_base64, tags=req.tags)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        store.event("rag_ingest_failed", filename=Path(req.filename).name[:120], error_type=type(exc).__name__)
        raise HTTPException(500, f"Document ingestion failed ({type(exc).__name__}). No content was added.") from exc
    store.event("rag_document_indexed", doc_id=result["doc_id"], filename=result["filename"],
                size_bytes=result["size_bytes"], chunks=result["chunk_count"],
                embedding_indexed=result["embedding_indexed"], redacted=result["secrets_redacted"])
    return {**result, "status": rag_engine.status()}

@app.post("/api/rag/index-workspace")
def rag_index_workspace(req: RAGWorkspaceIndexRequest):
    # Index only explicit workspace inventory entries; secret filters and path containment are rechecked.
    from .tools import is_sensitive_path, is_readable_text_file, safe_path, workspace_inventory
    report = {"indexed": [], "skipped": [], "failed": [], "bytes_read": 0, "max_files": req.max_files,
              "read_only": True, "note": "Only readable, non-sensitive text/code files in the selected workspace are considered."}
    candidates = workspace_inventory(limit=min(2000, req.max_files * 20))
    indexed_count = 0
    total_bytes = 0
    for item in candidates:
        if indexed_count >= req.max_files:
            report["skipped"].append({"path": item.get("path", "")[:240], "reason": "file_limit"})
            continue
        try:
            rel = str(item.get("path", ""))
            candidate = safe_path(rel)
            if not candidate.is_file() or is_sensitive_path(candidate) or not is_readable_text_file(candidate):
                report["skipped"].append({"path": rel[:240], "reason": "filtered_file"})
                continue
            size = candidate.stat().st_size
            if size > MAX_INGEST_BYTES:
                report["skipped"].append({"path": rel[:240], "reason": "file_size_limit"})
                continue
            if total_bytes + size > req.max_total_bytes:
                report["skipped"].append({"path": rel[:240], "reason": "total_byte_budget"})
                continue
            raw = candidate.read_bytes()
            result = rag_engine.ingest_bytes(candidate.name, "text/plain", raw, source="workspace:" + rel, tags=["workspace", candidate.suffix.lower().lstrip(".")])
            report["indexed"].append({"path": rel[:240], "doc_id": result["doc_id"], "chunk_count": result["chunk_count"], "size_bytes": size,
                                      "embedding_indexed": result["embedding_indexed"], "secrets_redacted": result["secrets_redacted"]})
            indexed_count += 1
            total_bytes += size
        except ValueError as exc:
            report["skipped"].append({"path": str(item.get("path", ""))[:240], "reason": str(exc)[:180]})
        except OSError as exc:
            report["failed"].append({"path": str(item.get("path", ""))[:240], "error": type(exc).__name__})
    report["bytes_read"] = total_bytes
    report["status"] = rag_engine.status()
    store.event("rag_workspace_indexed", indexed=len(report["indexed"]), skipped=len(report["skipped"]), failed=len(report["failed"]), bytes_read=total_bytes)
    return report

@app.post("/api/rag/search")
def rag_search(req: RAGSearchRequest):
    try:
        return rag_engine.search(req.query, req.limit, include_context=req.include_context)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.post("/api/rag/ask-context")
def rag_ask_context(req: RAGSearchRequest):
    try:
        return rag_engine.context_for_query(req.query, min(req.limit, 8))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.delete("/api/rag/documents/{doc_id}")
def rag_delete_document(doc_id: str):
    try:
        deleted = rag_engine.delete_document(doc_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not deleted:
        raise HTTPException(404, "Document not found in the local knowledge library.")
    store.event("rag_document_deleted", doc_id=doc_id)
    return {"deleted": True, "doc_id": doc_id, "status": rag_engine.status()}

@app.get("/api/knowledge/status")
def knowledge_status():
    config = knowledge_configuration()
    return {"enabled": bool(config.get("enabled")),
            "collection": config.get("collection") or None,
            "embedding_model": config.get("embedding_model") or None,
            "embedding_endpoint": safe_endpoint_label(str(config.get("embedding_endpoint", ""))) if config.get("embedding_endpoint") else None,
            "qdrant_endpoint": safe_endpoint_label(str(config.get("qdrant_endpoint", ""))) if config.get("qdrant_endpoint") else None,
            "read_only": True,
            "local_rag": rag_engine.status(),
            "detail": "Legacy Qdrant retrieval is enabled in read-only mode; the first-party local SQLite/FTS5 Knowledge Studio is available independently." if config.get("enabled") else "Legacy external Qdrant retrieval is disabled. The first-party local SQLite/FTS5 Knowledge Studio remains available at /api/rag/status."}

@app.get("/api/extensions")
def extensions_status():
    plugins = []
    for row in extensions.list_plugins():
        plugins.append({key: row.get(key) for key in ("id", "name", "description", "version", "enabled", "requested_enabled", "global_gate_enabled", "tools")})
    return {"skills": extensions.list_skills(), "plugins": plugins,
            "plugin_runtime": extensions.plugin_diagnostics(), "web": web_tools.cache_status(),
            "sandbox": sandbox.status(),
            "security": {"skills": "Markdown workflow text; never executes code", "plugins": "explicitly enabled loopback HTTP JSON only; no host-process code imports", "web": "public HTTPS static extraction with robots.txt checks, bounded same-host crawl and URL policy checks; DNS rebinding still requires network egress controls", "sandbox": "Docker opt-in, network disabled, disposable sanitized workspace copy"}}

@app.post("/api/extensions/reload")
def extensions_reload():
    # The registry intentionally scans manifests on demand: no executable modules or stale code cache.
    return {"ok": True, "skills": extensions.list_skills(),
            "plugins": [{key: row.get(key) for key in ("id", "name", "description", "version", "enabled", "requested_enabled", "global_gate_enabled", "tools")} for row in extensions.list_plugins()],
            "plugin_runtime": extensions.plugin_diagnostics(), "sandbox": sandbox.status()}

@app.get("/api/skills/{skill_id}")
def skill_detail(skill_id: str):
    result = extensions.load_skill(skill_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result

@app.get("/api/sandbox/status")
def sandbox_status():
    return sandbox.status()

@app.post("/api/web/search")
async def web_search_endpoint(req: WebSearchRequest):
    if os.getenv("INDRA_WEB_TOOLS_ENABLED", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(403, "Public web tools are disabled in .env.")
    result = await asyncio.to_thread(web_tools.search_web, req.query, req.limit)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

@app.post("/api/web/fetch")
async def web_fetch_endpoint(req: WebFetchRequest):
    if os.getenv("INDRA_WEB_TOOLS_ENABLED", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(403, "Public web tools are disabled in .env.")
    result = await asyncio.to_thread(web_tools.fetch_page, req.url, req.max_chars)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

@app.post("/api/web/research")
async def web_research_endpoint(req: WebResearchRequest):
    if os.getenv("INDRA_WEB_TOOLS_ENABLED", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(403, "Public web tools are disabled in .env.")
    result = await asyncio.to_thread(web_tools.research_web, req.query, req.max_pages, req.max_chars)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

@app.post("/api/web/crawl")
async def web_crawl_endpoint(req: WebCrawlRequest):
    if os.getenv("INDRA_WEB_TOOLS_ENABLED", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(403, "Public web tools are disabled in .env.")
    result = await asyncio.to_thread(web_tools.scrape_site, req.url, req.max_pages, req.max_chars)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

@app.post("/api/task-graph")
async def task_graph_endpoint(req: TaskGraphRequest):
    """Run an explicit bounded DAG of read-only child-agent tasks from the UI."""
    if len({row.id for row in req.tasks}) != len(req.tasks):
        raise HTTPException(422, "Task IDs must be unique.")
    if len(set(req.skills)) != len(req.skills) or any(not re.fullmatch(r"[a-z0-9_-]{1,100}", skill) for skill in req.skills):
        raise HTTPException(422, "Skills must be unique installed skill IDs.")
    valid_skill_ids = {row["id"] for row in extensions.list_skills()}
    unknown_skills = sorted(set(req.skills) - valid_skill_ids)
    if unknown_skills:
        raise HTTPException(422, "Unknown skill IDs: " + ", ".join(unknown_skills))
    if not run_slots.acquire():
        raise HTTPException(429, "The harness is at its concurrent-run limit. Wait for a run to finish.")
    graph_run_id = uuid.uuid4().hex
    started = time.perf_counter()
    try:
        try:
            max_seconds = max(15, min(240, int(os.getenv("INDRA_MAX_RUN_SECONDS", "240"))))
        except (TypeError, ValueError):
            max_seconds = 240
        store.event("task_graph_started", graph_run_id=graph_run_id, task_count=len(req.tasks),
                    max_concurrency=req.max_concurrency, skill_count=len(req.skills))
        def emit(kind, **payload):
            # Progress events intentionally record metadata only; task outputs are returned on completion.
            store.event("task_graph_event", graph_run_id=graph_run_id, event=kind,
                        task_id=str(payload.get("task_id", ""))[:40], status=str(payload.get("status", ""))[:40],
                        tool=str(payload.get("tool", ""))[:80])
        payload = {"tasks": [row.model_dump() for row in req.tasks], "max_concurrency": req.max_concurrency}
        try:
            result = await asyncio.wait_for(
                agent._run_task_graph(payload, (req.context or "")[:6000], req.skills, emit,
                                      time_budget_seconds=min(90, max_seconds)),
                timeout=max_seconds)
        except asyncio.TimeoutError as exc:
            store.event("task_graph_finished", graph_run_id=graph_run_id, status="time_limit",
                        duration_ms=round((time.perf_counter() - started) * 1000, 2))
            raise HTTPException(408, "Task graph exceeded its run-time budget. Child tasks were cancelled; inspect Run History.") from exc
        if "error" in result:
            store.event("task_graph_finished", graph_run_id=graph_run_id, status="rejected",
                        duration_ms=round((time.perf_counter() - started) * 1000, 2))
            raise HTTPException(422, result["error"])
        result["graph_run_id"] = graph_run_id
        store.event("task_graph_finished", graph_run_id=graph_run_id,
                    status="completed" if result.get("failed_or_skipped", 0) == 0 else "partial_failure",
                    completed=result.get("completed", 0), failed_or_skipped=result.get("failed_or_skipped", 0),
                    duration_ms=round((time.perf_counter() - started) * 1000, 2))
        return result
    finally:
        run_slots.release()

@app.post("/api/sandbox/propose-changes")
def sandbox_propose_changes(req: SandboxProposeRequest):
    """Convert selected ephemeral sandbox outputs into ordinary reviewable write proposals."""
    if len(set(req.paths)) != len(req.paths) or any(not path or "\x00" in path or len(path) > 2048 for path in req.paths):
        raise HTTPException(422, "Paths must be unique, non-empty workspace-relative file paths.")
    root = ensure_workspace().resolve()
    claimed = sandbox.claim_cached_result_files(req.sandbox_run_id, root, req.paths)
    if claimed is None:
        raise HTTPException(404, "Sandbox results expired, belong to another workspace, or one of the selected files is no longer available. Re-run the command and select the results again.")
    from .tools import propose_write
    proposals = []
    failures = []
    for path, content in claimed.items():
        result = propose_write(store, path, content,
                              reason=f"Sanitized output from Docker sandbox run {req.sandbox_run_id}; inspect diff before applying.")
        if result.get("status") == "approval_required":
            proposals.append({"action_id": result.get("action_id"), "path": result.get("path"),
                              "diff_preview": result.get("diff_preview", "")})
        else:
            failures.append({"path": path, "error": result.get("error", "Could not create proposal.")})
    store.event("sandbox_changes_proposed", sandbox_run_id=req.sandbox_run_id,
                proposal_count=len(proposals), failure_count=len(failures), paths=[p["path"] for p in proposals])
    if not proposals:
        raise HTTPException(422, {"message": "No reviewable write proposals were created. No workspace files were changed.", "failures": failures})
    return {"status": "approval_required", "sandbox_run_id": req.sandbox_run_id,
            "proposals": proposals, "failures": failures,
            "message": "Created reviewable proposals only. No host workspace file was changed; approve each diff in the Approval Queue."}


@app.post("/api/sandbox/run")
async def sandbox_run_endpoint(req: SandboxRunRequest):
    if not sandbox.status().get("ready"):
        raise HTTPException(503, "Docker sandbox is not ready. Install/start Docker Desktop and explicitly enable INDRA_ENABLE_DOCKER_SANDBOX=true.")
    if not run_slots.acquire():
        raise HTTPException(429, "The harness is at its concurrent-run limit. Wait for an active run to finish.")
    try:
        result = await asyncio.to_thread(sandbox.run_sandboxed, req.command, req.cwd, req.timeout_seconds, req.network_access)
        if "error" in result:
            raise HTTPException(400, result["error"])
        store.event("sandbox_run_finished", sandbox_run_id=result.get("sandbox_run_id"), return_code=result.get("return_code"), timed_out=result.get("timed_out"), duration_ms=result.get("duration_ms"), changed_files_count=result.get("changed_files_count"), network_access=req.network_access)
        return result
    finally:
        run_slots.release()

@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        prepared_attachments = prepare_chat_attachments(req.attachments)
    except AttachmentError as exc:
        raise HTTPException(422, str(exc)) from exc
    conversation_id = _start_conversation_turn(req)
    if not run_slots.acquire():
        if conversation_id:
            store.append_conversation_message(conversation_id, "assistant", "The harness is at its concurrent-run limit. No model run was started.", status="rejected")
            conversation_run_locks.release(conversation_id)
        raise HTTPException(429, "The harness is at its concurrent-run limit. Wait for a run to finish or cancel it.")
    try:
        run = await agent.run(req.message, req.history, context=req.context, mode=req.mode,
                              permission_requester=permission_broker.request,
                              attachment_context=prepared_attachments["text_context"],
                              image_attachments=prepared_attachments["images"],
                              attachment_count=prepared_attachments["count"],
                              **({"skills": req.skills} if req.skills else {}))
        _finish_conversation_turn(conversation_id, run)
        return run
    except Exception as exc:
        store.event("request_error", error_type=type(exc).__name__)
        if conversation_id:
            store.append_conversation_message(conversation_id, "assistant", "The request failed safely. Open Diagnostics and inspect the local server log.", status="failed")
        raise HTTPException(500, "The request failed safely. Open Diagnostics and inspect the local server log.")
    finally:
        _release_run(conversation_id)

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    try:
        prepared_attachments = prepare_chat_attachments(req.attachments)
    except AttachmentError as exc:
        raise HTTPException(422, str(exc)) from exc
    conversation_id = _start_conversation_turn(req)
    if not run_slots.acquire():
        if conversation_id:
            store.append_conversation_message(conversation_id, "assistant", "The harness is at its concurrent-run limit. No model run was started.", status="rejected")
            conversation_run_locks.release(conversation_id)
        raise HTTPException(429, "The harness is at its concurrent-run limit. Wait for a run to finish or cancel it.")
    queue: asyncio.Queue = asyncio.Queue(maxsize=512)
    overflow_tokens: list[str] = []
    overflow_chars = 0
    slot_released = False
    def release_slot():
        nonlocal slot_released
        if not slot_released:
            slot_released = True
            _release_run(conversation_id)
    def sink(event):
        nonlocal overflow_chars
        try: queue.put_nowait(event)
        except asyncio.QueueFull:
            if event.get("type") == "token":
                value = str(event.get("text", "")); room = max(0, 100000 - overflow_chars)
                if room:
                    overflow_tokens.append(value[:room]); overflow_chars += min(room, len(value))
            else:
                # On overload, preserve lifecycle/final events rather than letting the queue grow without bound.
                try: queue.get_nowait(); queue.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull): pass
    async def execute_run():
        try:
            run = await agent.run(req.message, req.history, event_sink=sink, stream=True, context=req.context,
                                  mode=req.mode, permission_requester=permission_broker.request,
                                  attachment_context=prepared_attachments["text_context"],
                                  image_attachments=prepared_attachments["images"],
                                  attachment_count=prepared_attachments["count"],
                                  **({"skills": req.skills} if req.skills else {}))
            _finish_conversation_turn(conversation_id, run)
            return run
        except Exception as exc:
            if conversation_id:
                store.append_conversation_message(conversation_id, "assistant", "The request failed safely. Open Diagnostics and inspect the local server log.", status="failed")
            raise
        finally:
            release_slot()
    task = asyncio.create_task(execute_run())
    async def event_generator():
        try:
            while True:
                if not queue.empty(): event = queue.get_nowait()
                elif overflow_tokens:
                    value = "".join(overflow_tokens); overflow_tokens.clear(); event = {"type": "token", "text": value}
                elif task.done(): break
                else:
                    if await request.is_disconnected(): task.cancel(); break
                    try: event = await asyncio.wait_for(queue.get(), timeout=8)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"; continue
                yield "data: " + json.dumps(event, ensure_ascii=False, default=str) + "\n\n"
                if event.get("type") == "run_finished": break
            if not task.done(): await task
            elif not task.cancelled(): task.result()
        except asyncio.CancelledError:
            task.cancel()
            try: await asyncio.wait_for(task, timeout=3)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception): pass
            raise
        except Exception as exc:
            yield "data: " + json.dumps({"type": "error", "message": f"Stream interrupted ({type(exc).__name__}). Check Diagnostics."}) + "\n\n"
        finally:
            if not task.done():
                task.cancel()
                try: await asyncio.wait_for(task, timeout=3)
                except (asyncio.CancelledError, asyncio.TimeoutError, Exception): pass
            # Idempotent: covers cancellation before execute_run's first scheduling turn.
            release_slot()
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"})

@app.get("/api/runs")
def runs(): return store.list_runs()[:100]

@app.get("/api/metrics")
def metrics():
    rows = store.list_runs()[:100]
    finished = [r for r in rows if r.get("status") not in {"running", "created"}]
    durations = sorted(float(r.get("duration_ms") or 0) for r in finished)
    by_status, by_profile = {}, {}; tool_errors = 0; tool_count = 0
    for run in finished:
        value = str(run.get("status", "unknown")); by_status[value] = by_status.get(value, 0) + 1
        profile = str(run.get("profile", "unknown")); by_profile[profile] = by_profile.get(profile, 0) + 1
        for trace in run.get("trace", []) or []:
            tool_count += 1; tool_errors += int(trace.get("category") != "ok")
    def percentile(frac):
        return durations[min(len(durations) - 1, int((len(durations) - 1) * frac))] if durations else None
    return {"sample_size": len(finished), "completed": by_status.get("completed", 0),
            "success_rate": round(by_status.get("completed", 0) / len(finished), 4) if finished else None,
            "median_duration_ms": percentile(.5), "p95_duration_ms": percentile(.95),
            "by_status": by_status, "by_profile": by_profile, "tool_calls": tool_count,
            "tool_error_rate": round(tool_errors / tool_count, 4) if tool_count else None,
            "scope": "Last 100 locally stored runs; operational telemetry, not a benchmark of model capability."}

@app.get("/api/feedback")
def get_run_feedback(conversation_id: str | None = Query(default=None, pattern=r"^[0-9a-f]{32}$")):
    """Return aggregate local ratings; run-level labels require a selected conversation ID."""
    return store.feedback_summary(conversation_id)

@app.post("/api/feedback")
def submit_run_feedback(req: RunFeedbackRequest):
    conversation = store.get_conversation(req.conversation_id)
    if not conversation:
        raise HTTPException(404, "Saved conversation not found.")
    messages = conversation.get("messages") if isinstance(conversation.get("messages"), list) else []
    if not any(
        isinstance(message, dict) and message.get("role") == "assistant" and message.get("run_id") == req.run_id
        for message in messages
    ):
        raise HTTPException(404, "That run is not part of this saved conversation.")
    try:
        record = store.set_run_feedback(req.run_id, req.conversation_id, req.rating)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"saved": True, "record": record, "summary": store.feedback_summary()}

@app.delete("/api/feedback/{run_id}")
def delete_run_feedback(run_id: str, conversation_id: str = Query(..., pattern=r"^[0-9a-f]{32}$")):
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise HTTPException(422, "Invalid run ID.")
    conversation = store.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(404, "Saved conversation not found.")
    messages = conversation.get("messages") if isinstance(conversation.get("messages"), list) else []
    if not any(
        isinstance(message, dict) and message.get("role") == "assistant" and message.get("run_id") == run_id
        for message in messages
    ):
        raise HTTPException(404, "That run is not part of this saved conversation.")
    return {"deleted": store.delete_run_feedback(run_id, conversation_id)}

@app.delete("/api/feedback")
def clear_run_feedback():
    return {"deleted": store.clear_run_feedback()}

@app.get("/api/actions")
def actions():
    fields = ("id", "created_at", "updated_at", "status", "kind", "path", "reason", "overwrites_existing",
              "expected_exists", "expected_sha256", "applied_sha256", "backup_path", "content", "diff", "conflict_reason", "undo_result")
    return [{key: action.get(key) for key in fields} for action in store.list_actions()[:100]]

@app.post("/api/actions/{aid}")
def decide(aid: str, req: Decision):
    action = next((item for item in store.list_actions() if item.get("id") == aid), None)
    if not action: raise HTTPException(404, "Action not found")
    if action.get("status") != "pending": raise HTTPException(409, "Action is no longer pending")
    if action.get("kind") != "write_file": raise HTTPException(400, "Unsupported action")
    action = store.claim_action(aid)
    if not action: raise HTTPException(409, "Action is already being processed or is no longer pending")
    if req.decision == "reject":
        store.update_action(aid, "rejected"); return {"status": "rejected", "id": aid}
    temp_path = None; backup_path = None
    try:
        target = safe_path(action["path"])
        if is_sensitive_path(target): raise PermissionError("Sensitive-path policy blocks this target.")
        target.parent.mkdir(parents=True, exist_ok=True)
        content = action.get("content", "")
        max_bytes = max(1024, min(int(os.getenv("INDRA_MAX_FILE_BYTES", "200000")), 5_000_000))
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > max_bytes: raise ValueError("Content exceeds the configured size limit.")
        if target.exists() and (target.is_dir() or not target.is_file()): raise ValueError("Target is not a regular file.")
        current_exists = target.exists()
        expected_exists = action.get("expected_exists", action.get("overwrites_existing", False))
        current_hash = _sha256_file(target) if current_exists else None
        if current_exists != bool(expected_exists):
            store.update_action(aid, "conflict", conflict_reason="Target existence changed after proposal creation.")
            raise HTTPException(409, "This proposal is stale: target existence changed. Ask the agent for a fresh proposal.")
        expected_hash = action.get("expected_sha256")
        if current_exists and not expected_hash:
            store.update_action(aid, "conflict", conflict_reason="Proposal has no verifiable target hash.")
            raise HTTPException(409, "This proposal predates target-hash protection. Create a fresh proposal rather than overwriting an unverified file.")
        if current_exists and current_hash != expected_hash:
            store.update_action(aid, "conflict", conflict_reason="Target content changed after proposal creation.")
            raise HTTPException(409, "This proposal is stale: the file changed after it was proposed. Ask the agent for a fresh proposal.")
        if current_exists:
            backup_root = _backup_root(); backup_root.mkdir(parents=True, exist_ok=True)
            backup_path = backup_root / f"{time.strftime('%Y%m%d-%H%M%S')}-{aid[:10]}-{target.name[:80]}.bak"
            shutil.copy2(target, backup_path)
            if _sha256_file(backup_path) != current_hash:
                backup_path.unlink(missing_ok=True); raise OSError("Backup verification failed.")
            if _sha256_file(target) != current_hash:
                raise HTTPException(409, "The file changed while preparing the backup; no write was applied.")
        with tempfile.NamedTemporaryFile("wb", prefix=".indra-", suffix=".tmp", dir=str(target.parent), delete=False) as temp:
            temp.write(content_bytes); temp.flush(); os.fsync(temp.fileno()); temp_path = Path(temp.name)
        # Recheck as late as possible: a user/editor may change the target during backup or staging.
        late_exists = target.exists()
        late_hash = _sha256_file(target) if late_exists else None
        if late_exists != current_exists or (late_exists and late_hash != current_hash):
            raise HTTPException(409, "The file changed while staging this proposal; no replacement was applied. Review the file and create a fresh proposal.")
        os.replace(temp_path, target); temp_path = None
        applied_hash = hashlib.sha256(content_bytes).hexdigest()
    except HTTPException:
        if temp_path:
            try: temp_path.unlink(missing_ok=True)
            except OSError: pass
        if any(item.get("id") == aid and item.get("status") == "applying" for item in store.list_actions()):
            store.update_action(aid, "conflict", conflict_reason="Stale or invalid target; write not applied.")
        raise
    except Exception as exc:
        if temp_path:
            try: temp_path.unlink(missing_ok=True)
            except OSError: pass
        store.update_action(aid, "failed", failure_type=type(exc).__name__)
        raise HTTPException(400, f"Could not apply proposal ({type(exc).__name__}). Inspect the target and server log.")
    store.update_action(aid, "approved", backup_path=str(backup_path) if backup_path else None,
                        applied_sha256=applied_hash, applied_at=time.time())
    store.event("action_applied", action_id=aid, path=action["path"], backup_created=bool(backup_path))
    return {"status": "approved", "id": aid, "path": action["path"], "backup_created": bool(backup_path)}

@app.post("/api/actions/{aid}/undo")
def undo_action(aid: str):
    action = next((item for item in store.list_actions() if item.get("id") == aid), None)
    if not action: raise HTTPException(404, "Action not found")
    if action.get("status") != "approved": raise HTTPException(409, "Only an applied proposal can be undone.")
    try:
        target = safe_path(action["path"])
        if is_sensitive_path(target): raise HTTPException(403, "Undo blocked by sensitive-path policy.")
        if not target.is_file() or _sha256_file(target) != action.get("applied_sha256"):
            raise HTTPException(409, "The file changed since the proposal was applied; refusing to overwrite newer work.")
        backup_value = action.get("backup_path")
        if backup_value:
            backup_root = _backup_root(); backup = Path(backup_value).resolve()
            if backup_root not in backup.parents or not backup.is_file():
                raise HTTPException(409, "Verified backup is unavailable; no file was changed.")
            expected_backup_hash = action.get("expected_sha256")
            if not expected_backup_hash or _sha256_file(backup) != expected_backup_hash:
                raise HTTPException(409, "Backup integrity could not be verified; no file was changed.")
            _atomic_write(target, backup.read_bytes()); result = "restored_backup"
        else:
            target.unlink(); result = "removed_created_file"
        store.update_action(aid, "undone", undo_result=result, undone_at=time.time())
        store.event("action_undone", action_id=aid, path=action["path"], result=result)
        return {"status": "undone", "id": aid, "path": action["path"], "result": result}
    except HTTPException: raise
    except (OSError, ValueError) as exc: raise HTTPException(400, f"Undo failed safely ({type(exc).__name__}).")

@app.get("/api/context")
def context(query: str = "", max_chars: int = 24000):
    if len(query) > 500: raise HTTPException(422, "Context query must be at most 500 characters.")
    return build_context_pack(query, max_chars)

@app.get("/api/git/status")
def git_status_endpoint():
    return git_tools.git_status()

@app.get("/api/workspace")
def workspace():
    return {"root": str(ensure_workspace()), "files": workspace_inventory(500), "file_limit": 500,
            "note": "Inventory excludes secrets, symlinks, dependency folders and build outputs."}

@app.get("/api/workspace/search")
def workspace_search(q: str = Query(min_length=1, max_length=500), directory: str = Query(default=".", max_length=2048)):
    """Bounded exact-text search across readable, non-sensitive project files."""
    if not q.strip():
        raise HTTPException(422, "Search query must not be empty.")
    result = search_files(q, directory)
    if "error" in result:
        message = result["error"]
        code = 403 if "escapes" in message.casefold() or "symlink" in message.casefold() else 404 if message == "Directory not found" else 400
        raise HTTPException(code, message)
    return result

@app.get("/api/workspace/read")
def workspace_read(path: str):
    try: target = safe_path(path)
    except ValueError as exc: raise HTTPException(403, str(exc))
    if is_sensitive_path(target): raise HTTPException(403, "Reading files that may contain secrets is blocked.")
    if not target.is_file(): raise HTTPException(404, "File not found")
    if not is_readable_text_file(target):
        raise HTTPException(415, "This file type is not enabled for preview.")
    try:
        if target.stat().st_size > max(1024, min(int(os.getenv("INDRA_MAX_FILE_BYTES", "200000")), 5_000_000)):
            raise HTTPException(413, "File exceeds the configured size limit.")
        return {"path": str(target.relative_to(ensure_workspace())).replace("\\", "/"), "content": target.read_text(encoding="utf-8")}
    except UnicodeDecodeError: raise HTTPException(415, "Only UTF-8 text files can be previewed.")
    except OSError as exc: raise HTTPException(400, f"File could not be previewed ({type(exc).__name__}).")

@app.get("/api/hmi/audit")
def hmi_audit():
    """Read-only static UI heuristic audit; not a formal accessibility certification."""
    return hmi.audit_frontend(STATIC)


@app.get("/api/capsules")
def list_capsules():
    """List local Capsules; the list operation does not execute archived code."""
    return {"capsules": capsule_service.list(), "signer_fingerprint_sha256": capsule_service.fingerprint}

@app.post("/api/capsules")
def create_capsule(req: CapsuleCreateRequest):
    """Create a signed, passive snapshot. Only explicitly selected workspace files are included."""
    run = None
    current_workspace = ensure_workspace().resolve()
    if req.run_id:
        run = next((item for item in store.list_runs() if str(item.get("run_id")) == req.run_id), None)
        if run is None:
            raise HTTPException(404, "Run was not found in local run history.")
        saved_workspace = run.get("workspace")
        if saved_workspace:
            try:
                if Path(str(saved_workspace)).resolve(strict=True) != current_workspace:
                    raise HTTPException(409, "The selected run belongs to another workspace. Switch workspaces before creating its Capsule.")
            except OSError:
                raise HTTPException(409, "The selected run workspace is unavailable. Reopen the original workspace before creating its Capsule.")
    events = store.list_events(200) if req.include_recent_event_metadata else []
    if req.run_id:
        events = [event for event in events if str(event.get("run_id") or "") == req.run_id]
    try:
        result = capsule_service.create(current_workspace, run=run, events=events, paths=req.workspace_paths)
    except (ValueError, OSError) as exc:
        raise HTTPException(422, str(exc))
    store.event("capsule_created", capsule_id=result["capsule_id"], file_count=result["file_count"], run_id=req.run_id)
    return {**result, "signature": "Ed25519", "signer_fingerprint_note": "Keep/pin this fingerprint to recognize Capsules signed by this Origo installation."}

@app.post("/api/capsules/{capsule_id}/verify")
def verify_capsule(capsule_id: str):
    try:
        path = capsule_service.path_for(capsule_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    return capsule_service.verify(path)

@app.get("/api/capsules/{capsule_id}/receipt")
def capsule_receipt(capsule_id: str):
    """Download a static HTML integrity receipt. It does not contain workspace file contents."""
    from html import escape
    try:
        path = capsule_service.path_for(capsule_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    verification = capsule_service.verify(path)
    try:
        import zipfile
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            manifest_info = archive.getinfo("capsule_manifest.json")
            if manifest_info.file_size > 1_000_000 or len(infos) > 600 or sum(info.file_size for info in infos) > 50 * 1024 * 1024:
                raise ValueError("Capsule manifest or expanded archive exceeds the receipt safety limit.")
            manifest = json.loads(archive.read("capsule_manifest.json"))
    except Exception as exc:
        raise HTTPException(422, f"Capsule manifest could not be read ({type(exc).__name__}).")
    status_text = "Integrity verified" if verification.get("valid") else "Verification failed or incomplete"
    status_color = "#176b43" if verification.get("valid") else "#8d3333"
    file_rows = "".join(
        "<tr><td>" + escape(str(item.get("path", ""))) + "</td><td>" + escape(str(item.get("size", ""))) + "</td><td><code>" + escape(str(item.get("sha256", ""))) + "</code></td></tr>"
        for item in manifest.get("files", []) if isinstance(item, dict)
    ) or '<tr><td colspan="3">Metadata-only Capsule; no workspace payload files.</td></tr>'
    problems = "".join("<li>" + escape(str(problem)) + "</li>" for problem in verification.get("problems", [])) or "<li>None reported.</li>"
    trusted_text = "Signer fingerprint matches this installation" if verification.get("signer_trusted_by_this_install") else "Signer is not pinned/trusted by this installation"
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';"><title>Origo Capsule Integrity Receipt</title><style>body{{font:16px/1.55 system-ui,sans-serif;max-width:1100px;margin:36px auto;padding:0 18px;color:#17212b}}h1{{font-size:30px}}.status{{padding:14px 16px;border-radius:9px;background:{status_color};color:white;font-weight:700}}.note{{border-left:4px solid #c28d31;padding:10px 14px;background:#fff6df}}code{{overflow-wrap:anywhere;font-size:12px}}table{{border-collapse:collapse;width:100%;margin-top:18px}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #d7dfe6;vertical-align:top}}th{{background:#eff3f6}}td code{{word-break:break-all}}.muted{{color:#4e5d6c;font-size:13px}}@media(max-width:680px){{table{{font-size:12px}}th,td{{padding:6px}}}}</style></head><body><p class="muted">INDRA ORIGO · CAPSULE RECEIPT</p><h1>Research artifact integrity receipt</h1><div class="status">{escape(status_text)}</div><p>This receipt summarizes a local verification result at generation time. It does not prove scientific validity, semantic correctness, or signer identity on its own. Verify the ZIP independently and compare the signer fingerprint through a trusted channel.</p><div class="note">{escape(trusted_text)}.</div><h2>Capsule metadata</h2><p><b>Capsule ID:</b> <code>{escape(str(manifest.get('capsule_id', 'unknown')))}</code><br><b>Created:</b> {escape(str(manifest.get('created_at', 'unknown')))}<br><b>Archive SHA-256:</b> <code>{escape(str(_sha256_file(path) or 'unavailable'))}</code><br><b>Signer fingerprint SHA-256:</b> <code>{escape(str(verification.get('signer_fingerprint_sha256', 'unavailable')))}</code></p><p><b>Signature valid:</b> {str(bool(verification.get('signature_valid'))).lower()} · <b>File hashes valid:</b> {str(bool(verification.get('files_valid'))).lower()} · <b>Manifest valid:</b> {str(bool(verification.get('manifest_valid'))).lower()}</p><h2>Manifest files</h2><table><thead><tr><th>Path</th><th>Bytes</th><th>SHA-256</th></tr></thead><tbody>{file_rows}</tbody></table><h2>Verification findings</h2><ul>{problems}</ul><p class="muted">Generated by Indra Origo {escape(app.version)}. No archived code was executed to create this receipt.</p></body></html>'''
    return HTMLResponse(page, headers={"Content-Disposition": f'attachment; filename="{capsule_id}-receipt.html"'})

@app.get("/api/capsules/{capsule_id}/download")
def download_capsule(capsule_id: str):
    try:
        path = capsule_service.path_for(capsule_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    return FileResponse(path, media_type="application/zip", filename=path.name)

@app.get("/api/proof/ledger")
def get_proof_ledger():
    return proof_ledger.get()

@app.post("/api/proof/evidence")
def add_proof_evidence(req: ProofEvidenceRequest):
    try:
        item = proof_ledger.add_evidence(ensure_workspace(), req.path, req.excerpt, req.note)
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        raise HTTPException(422, str(exc))
    store.event("proof_evidence_added", evidence_id=item["evidence_id"], path=item["path"], source_sha256=item["source_sha256"])
    return item

@app.post("/api/proof/claims")
def add_proof_claim(req: ProofClaimRequest):
    try:
        item = proof_ledger.add_claim(req.statement, req.evidence_ids, workspace=ensure_workspace())
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    store.event("proof_claim_added", claim_id=item["claim_id"], status=item["status"], evidence_count=len(item["evidence_ids"]))
    return item

@app.post("/api/proof/claims/{claim_id}/review")
def review_proof_claim(claim_id: str, req: ProofClaimReviewRequest):
    try:
        item = proof_ledger.review_claim(claim_id, req.reviewed, workspace=ensure_workspace())
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    store.event("proof_claim_reviewed", claim_id=claim_id, reviewed=req.reviewed, resulting_status=item["status"])
    return item

@app.post("/api/proof/lint")
def lint_proof_text(req: ProofLintRequest):
    report = proof_ledger.lint(req.text, req.claim_ids, workspace=ensure_workspace())
    report["policy"] = "export gate is advisory for callers; exports not yet globally wired to this endpoint"
    return report

@app.get("/api/scout/status")
def scout_status():
    return {"agent": "Origo Scout", "version": "1.0", "available": True,
            "scope": "bounded read-only application self-tests",
            "model_inference": False, "outbound_network": False,
            "writes": False, "approvals_granted": False}

@app.post("/api/scout/run")
def scout_run():
    """Run deterministic, read-only self-checks; never invokes an LLM."""
    return scout.run_scout(app)

@app.get("/api/amplifier/status")
def amplifier_status():
    return {
        "status": "implemented_primitives",
        "features": {
            "typed_plan_validation": "implemented and tested",
            "context_budgeting": "implemented and tested; approximate character-based token estimate",
            "deterministic_verifiers": "implemented and tested",
            "capability_profile_format": "implemented and tested; live model probe suite not yet implemented",
            "best_of_n": "scaffold only",
            "amplifier_vs_baseline_benchmark": "scaffold only",
        },
        "policy": "Model output is untrusted input; validation and safety limits are enforced by the harness.",
    }

@app.post("/api/amplifier/plan/validate")
def amplifier_validate_plan(req: PlanValidationRequest):
    try:
        plan = amplifier.validate_plan(req.plan)
    except amplifier.ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"valid": True, "plan": plan, "step_count": len(plan["steps"])}

@app.post("/api/amplifier/context/pack")
def amplifier_pack_context(req: ContextPackRequest):
    try: return amplifier.pack_context(req.items, req.token_budget)
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc

@app.post("/api/amplifier/verify")
def amplifier_verify(req: VerifyStepRequest):
    try: return amplifier.verify_result(req.verifier, req.result, req.expected)
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc

@app.post("/api/amplifier/verify/arithmetic")
def amplifier_verify_arithmetic(req: ArithmeticVerifyRequest):
    return amplifier.verify_arithmetic(req.expression, req.claimed, req.tolerance)

@app.post("/api/amplifier/tokens/estimate")
def amplifier_token_estimate(req: TokenEstimateRequest):
    return {"estimated_tokens": amplifier.estimate_tokens(req.text), "characters": len(req.text),
            "method": "ceil(characters/3)", "exact": False,
            "note": "Use provider tokenization for exact billing or context-window accounting."}

@app.post("/api/amplifier/profile")
def amplifier_profile(req: CapabilityProfileRequest):
    return amplifier.capability_profile(req.results)

@app.get("/assets/{name}")
def assets(name: str):
    target = (STATIC / name).resolve()
    if STATIC.resolve() not in target.parents or not target.is_file(): raise HTTPException(404, "Asset not found")
    return FileResponse(target)
