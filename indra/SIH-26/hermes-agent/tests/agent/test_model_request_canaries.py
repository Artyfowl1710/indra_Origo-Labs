"""Real plugin discovery + SDK HTTP transport, with an isolated local receiver."""
import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest


@contextmanager
def receiver(status=200):
    received = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            # Agent initialization also probes model metadata. Count inference
            # requests separately; metadata has no conversation content.
            if self.path.endswith("/chat/completions"): received.append(payload)
            body = json.dumps({"id":"fixture", "object":"chat.completion", "created":1, "model":"fixture",
                "choices":[{"index":0,"message":{"role":"assistant","content":"Fixture reply"},"finish_reason":"stop"}],
                "usage":{"prompt_tokens":5,"completion_tokens":2,"total_tokens":7}}).encode()
            if status != 200: body = json.dumps({"error":{"message":"Fixture credit exhausted","type":"payment_required"}}).encode()
            self.send_response(status); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try: yield "http://127.0.0.1:%s/v1" % server.server_port, received
    finally: server.shutdown(); server.server_close(); thread.join(timeout=2)


@pytest.fixture
def guarded(monkeypatch, tmp_path):
    # A resolver regression must never escape the fixture receivers, including
    # during metadata probes or an unexpected fallback to a public provider.
    import socket
    original_lookup = socket.getaddrinfo
    def local_lookup(host, *args, **kwargs):
        if host not in {None, "localhost", "127.0.0.1", "::1", b"localhost", b"127.0.0.1", b"::1"}:
            raise OSError("Nonlocal network disabled in canary acceptance fixture")
        return original_lookup(host, *args, **kwargs)
    monkeypatch.setattr(socket, "getaddrinfo", local_lookup)
    home = tmp_path / "profile"; home.mkdir()
    (home / "config.yaml").write_text("security:\n  untrusted_content_guard: true\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(home))
    from hermes_cli.origo_workspace import workspace
    current = workspace(); current.shared_root = tmp_path / "machine-data"
    marker = current.canaries().create("fixture-owner")["token"]
    from hermes_cli.plugins import discover_plugins
    discover_plugins()
    return current, marker


def test_real_auxiliary_sync_async_and_stream_do_not_reach_receiver(guarded):
    from agent.auxiliary_client import call_llm, async_call_llm
    from agent.model_request_policy import ModelRequestBlocked
    current, marker = guarded
    with receiver() as (url, received):
        kwargs = dict(provider="custom", model="fixture", base_url=url, api_key="fixture-local-key",
                      messages=[{"role":"user","content":marker}], max_tokens=20)
        for stream in [False, True]:
            with pytest.raises(ModelRequestBlocked): call_llm(**kwargs, stream=stream)
        with pytest.raises(ModelRequestBlocked): asyncio.run(async_call_llm(**kwargs))
        assert received == []
        kwargs["messages"] = [{"role":"user","content":"Clean fixture"}]
        assert call_llm(**kwargs).choices[0].message.content == "Fixture reply"
        assert asyncio.run(async_call_llm(**kwargs)).choices[0].message.content == "Fixture reply"
        assert len(received) == 2
    assert current.audit.verify()["valid"]
    assert marker not in json.dumps(current.audit.recent())


def test_main_loop_refuses_without_recovery_or_transmission(guarded):
    from run_agent import AIAgent
    _, marker = guarded
    with receiver() as (url, received):
        agent = AIAgent(provider="custom", model="fixture", base_url=url, api_key="fixture-local-key",
                        max_iterations=2, enabled_toolsets=[], quiet_mode=True,
                        skip_memory=True, skip_context_files=True, skip_background_review=True)
        # The fake receiver returns a complete response, not SSE.
        agent._disable_streaming = True
        result = agent.run_conversation(marker)
        assert result["failure_reason"] == "outbound_policy"
        assert result["failure_retryable"] is False
        assert received == []
        assert marker not in result["final_response"]


def test_relay_unmanaged_physical_attempts_block_before_callback(guarded):
    from agent import relay_llm
    from agent.model_request_policy import ModelRequestBlocked
    _, marker = guarded
    calls = []
    request = {"messages":[{"role":"user","content":marker}]}
    with pytest.raises(ModelRequestBlocked):
        relay_llm.execute(request, lambda body: calls.append(body), name="fixture", model_name="fixture")
    with pytest.raises(ModelRequestBlocked):
        asyncio.run(relay_llm.execute_async(request, lambda body: calls.append(body), name="fixture", model_name="fixture"))
    with pytest.raises(ModelRequestBlocked):
        relay_llm.stream_current(request, lambda body: calls.append(body), name="fixture", model_name="fixture", finalizer=lambda:None)
    with pytest.raises(ModelRequestBlocked):
        relay_llm.stream(request, lambda body: calls.append(body), session_id="fixture", name="fixture", model_name="fixture", finalizer=lambda:None)
    assert calls == []


def test_tool_registry_canary_veto_cannot_be_overridden(guarded, monkeypatch):
    import model_tools
    from tools.registry import registry
    from tools import approval
    current, marker = guarded; calls = []
    monkeypatch.setattr(approval, "_yolo_active", lambda:True)
    registry.register(name="fixture_canary_send", toolset="fixture", schema={"name":"fixture_canary_send","parameters":{"type":"object","properties":{}}},
                      handler=lambda args,**kw: calls.append(args) or "sent", check_fn=lambda:True)
    try:
        result = model_tools.handle_function_call("fixture_canary_send", {"body":marker}, session_id="chat", turn_id="turn")
        assert calls == []
        assert "canary" in str(result).lower()
        assert marker not in str(result)
        assert any(row["kind"] == "security.canary_blocked" for row in current.audit.recent())
    finally: registry.deregister("fixture_canary_send")


def test_policy_hook_failure_and_invalid_directive_fail_closed(guarded):
    from hermes_cli.plugins import get_plugin_manager
    from agent.model_request_policy import enforce_model_request, ModelRequestBlocked
    manager = get_plugin_manager()
    def broken(request): raise RuntimeError("private request text")
    manager._hooks["pre_model_request"].append(broken)
    with pytest.raises(ModelRequestBlocked) as error: enforce_model_request({"messages":[]})
    assert "private request text" not in str(error.value)
    manager._hooks["pre_model_request"].remove(broken)
    manager._hooks["pre_model_request"].append(lambda request: {"action":"modify","request":{}})
    with pytest.raises(ModelRequestBlocked): enforce_model_request({"messages":[]})


def test_policy_timeout_and_suppressed_worker_cannot_allow(guarded, monkeypatch):
    import time
    import hermes_cli.plugins as plugins
    from agent.model_request_policy import enforce_model_request, ModelRequestBlocked
    manager = plugins.get_plugin_manager()
    monkeypatch.setattr(plugins, "_resolve_hook_callback_timeout", lambda:0.03)
    def stalled(request): time.sleep(0.2)
    manager._hooks["pre_model_request"].append(stalled)
    for _ in range(2):
        with pytest.raises(ModelRequestBlocked): enforce_model_request({"messages":[]})


def test_voice_http_turn_and_transcription_refuse_before_network(guarded, monkeypatch):
    import base64
    from starlette.testclient import TestClient
    from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN
    from hermes_cli import voice_connections
    from hermes_cli.web_routers import indra_voice as voice
    current, marker = guarded
    with receiver() as (url, received), TestClient(app) as client:
        client.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN
        monkeypatch.setattr(voice_connections,"resolve",lambda *args:(url,"fixture-local-key"))
        request = {"provider":"custom:fixture","model":"fixture","text":marker}
        response = client.post("/api/indra/voice/turn",json=request)
        assert response.status_code == 403 and received == []
        assert marker not in response.text
        request["text"] = "Clean fixture"
        response = client.post("/api/indra/voice/turn",json=request)
        assert response.status_code == 200
        assert response.json()["text"] == "Fixture reply" and len(received) == 1
        monkeypatch.setattr(voice,"credentials",lambda request:(str(current.home),"fixture-local-key"))
        response = client.post("/api/indra/voice/transcribe",json={"data_url":"data:audio/wav;base64,"+base64.b64encode(marker.encode()).decode()})
        assert response.status_code == 403
        assert len(received) == 1
        assert current.audit.verify()["valid"]


def test_explicit_cloud_vision_fallback_reaches_only_configured_receiver(guarded):
    import yaml
    from agent.auxiliary_client import call_llm
    from agent.model_request_policy import ModelRequestBlocked
    current, marker = guarded
    with receiver(402) as (primary, primary_calls), receiver() as (secondary, secondary_calls):
        cfg = {"security":{"untrusted_content_guard":True}, "auxiliary":{"vision":{"fallback_chain":[{
            "provider":"custom","model":"fixture-secondary","base_url":secondary,"api_key":"fixture-local-key"}]}}}
        (current.home/"config.yaml").write_text(yaml.safe_dump(cfg),encoding="utf-8")
        kwargs = dict(task="vision",provider="openrouter",model="fixture-primary",base_url=primary,
                      api_key="fixture-local-key",messages=[{"role":"user","content":"Clean fixture"}],max_tokens=20)
        assert call_llm(**kwargs).choices[0].message.content == "Fixture reply"
        assert len(primary_calls) == 1 and len(secondary_calls) == 1
        kwargs["messages"] = [{"role":"user","content":marker}]
        with pytest.raises(ModelRequestBlocked): call_llm(**kwargs)
        assert len(primary_calls) == 1 and len(secondary_calls) == 1


@pytest.mark.parametrize("endpoint", ["http://remote.example/v1", "ftp://127.0.0.1/v1",
    "https://user:password@remote.example/v1", "https://remote.example/v1?key=fixture", "https://remote.example/v1#secret"])
def test_openrouter_override_rejects_unsafe_endpoints_before_connecting(guarded, endpoint):
    from agent.auxiliary_client import resolve_provider_client
    with pytest.raises(ValueError):
        resolve_provider_client("openrouter",model="fixture",explicit_base_url=endpoint,explicit_api_key="fixture-local-key")
