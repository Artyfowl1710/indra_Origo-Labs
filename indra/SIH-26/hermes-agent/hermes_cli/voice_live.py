"""Authenticated, bounded Live voice bridge. Provider credentials stay server-side."""
import asyncio
from collections import deque
from contextlib import suppress
import json
import logging
import threading
import time
import uuid

from fastapi import WebSocketDisconnect, HTTPException
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from agent.model_request_policy import ModelRequestBlocked, enforce_model_request
from hermes_cli.web_server_profiles import _config_profile_scope

LIVE_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
MAX_FRAME_CHARS = 256 * 1024
MAX_UPSTREAM_BYTES = 2 * 1024 * 1024
SETUP_TIMEOUT = 20
SESSION_SECONDS = 30 * 60
TEXT_WINDOW = 8192

# A private logger cannot emit handshake credentials under a global DEBUG setting.
_transport_log = logging.Logger("indra.voice.transport", level=logging.CRITICAL)
_transport_log.propagate = False


class LiveFrameError(ValueError):
    pass


class UpstreamVoiceError(RuntimeError):
    pass


class SessionLimiter:
    """Loop-independent counters: TestClient and production can use distinct loops."""
    def __init__(self, total=8, per_profile=2, per_minute=6):
        self.total = total; self.per_profile = per_profile; self.per_minute = per_minute
        self.lock = threading.Lock(); self.active = {}; self.attempts = {}

    def acquire(self, home):
        now = time.monotonic()
        with self.lock:
            self.attempts = {h: [t for t in times if now-t < 60] for h,times in self.attempts.items()}
            self.attempts = {h: times for h,times in self.attempts.items() if times}
            if len(self.active) >= self.total or sum(h == home for h in self.active.values()) >= self.per_profile:
                raise LiveFrameError("Voice connection limit reached. Close another voice session and retry.")
            if len(self.attempts) >= 1024 or len(self.attempts.get(home, [])) >= self.per_minute:
                raise LiveFrameError("Voice reconnect limit reached. Wait a minute and retry.")
            ident = uuid.uuid4().hex
            self.active[ident] = home; self.attempts.setdefault(home, []).append(now)
            return ident

    def release(self, ident):
        with self.lock: self.active.pop(ident, None)


limiter = SessionLimiter()


def parse_frame(raw, *, first=False, model=""):
    if not isinstance(raw, str) or len(raw) > MAX_FRAME_CHARS:
        raise LiveFrameError("Voice frame is too large or is not JSON text.")
    try:
        def invalid_constant(value): raise ValueError("Nonfinite JSON number")
        def unique_object(pairs):
            value = {}
            for key, item in pairs:
                if key in value: raise ValueError("Duplicate JSON key")
                value[key] = item
            return value
        value = json.loads(raw, parse_constant=invalid_constant, object_pairs_hook=unique_object)
    except (ValueError, RecursionError):
        raise LiveFrameError("Invalid voice JSON frame.") from None
    allowed = {"setup"} if first else {"realtimeInput", "clientContent", "toolResponse"}
    if not isinstance(value, dict) or len(value) != 1 or not set(value) <= allowed:
        raise LiveFrameError("Unexpected voice message. Start a new voice session.")
    body = next(iter(value.values()))
    if not isinstance(body, dict): raise LiveFrameError("Invalid voice message body.")
    if first and body.get("model") != "models/" + model:
        raise LiveFrameError("Voice setup must use the selected model.")
    return value


def text_tail(frame):
    """Bounded semantic-text window across frames; do not retain opaque media."""
    parts = deque(); length = 0; stack = [(frame, 0)]; nodes = 0
    while stack:
        value, depth = stack.pop(); nodes += 1
        if depth > 64 or nodes > 20_000: raise LiveFrameError("Voice frame structure limit exceeded.")
        if isinstance(value, dict):
            media = str(value.get("mimeType", "")).startswith(("audio/", "video/", "image/"))
            if media: continue
            entries = list(value.items())
            stack.extend((v, depth+1) for _,v in reversed(entries))
        elif isinstance(value, list): stack.extend((v, depth+1) for v in reversed(value))
        elif isinstance(value, str):
            chunk = value[-TEXT_WINDOW:]; parts.append(chunk); length += len(chunk)
            while len(parts) > 1 and length-len(parts[0]) >= TEXT_WINDOW: length -= len(parts.popleft())
    return "".join(parts)[-TEXT_WINDOW:]


def check_frame(profile, frame, recent, session, sequence):
    tail = text_tail(frame)
    with _config_profile_scope(profile):
        enforce_model_request({"frame":frame, "recent_text":recent+tail}, task="voice-live",
                              provider="google", session_id=session, turn_id="frame-"+str(sequence))
    return (recent+tail)[-TEXT_WINDOW:]


async def _error(ws, code, message, close=1008):
    with suppress(Exception): await ws.send_json({"error":{"code":code,"message":message}})
    with suppress(Exception): await ws.close(code=close)


async def bridge(ws, *, credentials, models):
    """One authenticated local socket owns exactly one fixed-provider upstream socket."""
    from hermes_cli.web_server_chat import _ws_auth_ok, _ws_request_is_allowed
    if not _ws_request_is_allowed(ws):
        await ws.close(code=4403); return
    if not _ws_auth_ok(ws):
        await ws.close(code=4401); return
    model = ws.query_params.get("model", "")
    if model not in models:
        await ws.close(code=4400); return
    profile = ws.query_params.get("profile") or None
    session = None; tasks = []; outcome = "unavailable"; count = 0; bytes_sent = 0; current = None
    try:
        home, key = await asyncio.to_thread(credentials, ws)
        await ws.accept()
        if not key:
            await _error(ws,"not_configured","Add a key for the selected voice connection in Runtime."); return
        session = limiter.acquire(home)
        raw = await asyncio.wait_for(ws.receive_text(), SETUP_TIMEOUT)
        frame = parse_frame(raw, first=True, model=model)
        recent = await asyncio.to_thread(check_frame, profile, frame, "", session, 0)
        from hermes_cli.origo_workspace import workspace
        current = workspace(home)
        # Failed provenance stops before provider connection/transmission.
        current.audit.append("voice.live_started",{
            "session":session,"provider":"google","model":model,"transport":"local-bridge"})
        async with connect(LIVE_URL, additional_headers={"x-goog-api-key":key}, proxy=None,
                           compression=None, open_timeout=20, close_timeout=2,
                           max_size=MAX_UPSTREAM_BYTES, max_queue=4, write_limit=65536,
                           logger=_transport_log) as upstream:
            await upstream.send(raw); count = 1; bytes_sent = len(raw.encode("utf-8"))
            await ws.send_json({"indraSession":{"id":session}})

            async def outgoing():
                nonlocal recent, count, bytes_sent
                while True:
                    raw = await ws.receive_text()
                    frame = parse_frame(raw)
                    recent = await asyncio.to_thread(check_frame, profile, frame, recent, session, count)
                    await upstream.send(raw)
                    count += 1; bytes_sent += len(raw.encode("utf-8"))

            async def incoming():
                async for raw in upstream:
                    if isinstance(raw, bytes): raw = raw.decode("utf-8")
                    if len(raw.encode("utf-8")) > MAX_UPSTREAM_BYTES:
                        raise LiveFrameError("Voice response exceeded the transport limit.")
                    parsed = json.loads(raw)
                    if not isinstance(parsed, dict) or parsed.get("error"):
                        raise UpstreamVoiceError("Provider returned an invalid response or error")
                    await ws.send_text(raw)

            tasks = [asyncio.create_task(outgoing()), asyncio.create_task(incoming())]
            try:
                done, _ = await asyncio.wait(tasks, timeout=SESSION_SECONDS, return_when=asyncio.FIRST_COMPLETED)
                if not done:
                    outcome = "rotation"; await ws.close(code=1012)
                else:
                    errors = [t.exception() for t in done if not t.cancelled() and t.exception()]
                    blocked = next((e for e in errors if isinstance(e, ModelRequestBlocked)), None)
                    if blocked: raise blocked
                    if errors: raise errors[0]
                    outcome = "upstream_closed"
                    await ws.close(code=1000)
            finally:
                for task in tasks: task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
    except ModelRequestBlocked:
        outcome = "policy_blocked"
        await _error(ws,"outbound_policy","Voice transmission stopped by the local outbound policy. Inspect Audit.")
    except LiveFrameError as error:
        outcome = "invalid_or_limited"
        await _error(ws,"voice_input",str(error))
    except UpstreamVoiceError:
        outcome = "provider_error"
        await _error(ws,"provider_error","Voice provider rejected this request. Check its access and quota.")
    except WebSocketDisconnect:
        outcome = "client_disconnected"
    except asyncio.CancelledError:
        outcome = "cancelled"
        raise
    except asyncio.TimeoutError:
        outcome = "setup_timeout"
        await _error(ws,"setup_timeout","Voice setup timed out. Start voice again.")
    except ConnectionClosed as error:
        outcome = "upstream_closed"
        # Never copy a provider's close reason, URL, headers or key to the client.
        with suppress(Exception): await ws.close(code=1008 if error.rcvd and error.rcvd.code == 1008 else 1011)
    except HTTPException:
        await _error(ws,"profile_unavailable","Selected voice profile is unavailable.")
    except Exception:
        await _error(ws,"voice_unavailable","Voice connection is unavailable. Check its key, access and quota.")
    finally:
        for task in tasks: task.cancel()
        if tasks: await asyncio.gather(*tasks, return_exceptions=True)
        if session:
            try:
                if current:
                    # This final local transaction has no cancellation checkpoint;
                    # a disconnected client must not cancel its provenance receipt.
                    try:
                        current.audit.append("voice.live_ended",{
                            "session":session,"provider":"google","model":model,"outcome":outcome,
                            "sent_frames":count,"sent_bytes":bytes_sent})
                    except Exception as error:
                        logging.getLogger(__name__).warning("Voice completion audit could not be saved (%s)",type(error).__name__)
            finally:
                limiter.release(session)
