"""Real local WebSocket receiver and ASGI route, isolated profiles and canaries."""
from contextlib import contextmanager
import json
import logging
from pathlib import Path
import threading
import time
from urllib.parse import urlencode

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from websockets.sync.server import serve
from websockets.exceptions import ConnectionClosed

from hermes_cli import voice_live as live
from hermes_cli.web_routers import indra_voice as voice

MODEL = voice.MODELS[0]
SETUP = {"setup":{"model":"models/"+MODEL,"generationConfig":{"responseModalities":["AUDIO"]}}}


@contextmanager
def receiver():
    frames = []; headers = []; sockets = []; closed = threading.Event()
    def handler(socket):
        sockets.append(socket); headers.append(socket.request.headers.get("x-goog-api-key"))
        try:
            for raw in socket:
                frame = json.loads(raw); frames.append(frame)
                if "setup" in frame: socket.send(json.dumps({"setupComplete":{},"sessionResumptionUpdate":{"resumable":True,"newHandle":"fixture-resume"}}))
                elif frame.get("realtimeInput",{}).get("text") == "provider-error":
                    socket.send(json.dumps({"error":{"message":"private-provider-detail "+headers[-1]}}))
                else: socket.send(json.dumps({"serverContent":{"turnComplete":True,"outputTranscription":{"text":"Fixture reply"},"modelTurn":{"parts":[{"inlineData":{"mimeType":"audio/pcm;rate=24000","data":"AAA="}}]}}}))
        except ConnectionClosed: pass
        finally: closed.set()
    logger = logging.Logger("fixture.live.receiver",level=logging.CRITICAL); logger.propagate = False
    with serve(handler,"127.0.0.1",0,compression=None,logger=logger) as server:
        thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try: yield {"url":"ws://127.0.0.1:%s"%server.socket.getsockname()[1],"frames":frames,"headers":headers,"closed":closed}
        finally:
            for socket in sockets: socket.close()
            server.shutdown(); thread.join(timeout=3)


@pytest.fixture
def environment(monkeypatch,tmp_path):
    from hermes_cli import web_server, profiles
    from hermes_cli.origo_workspace import workspace
    home = tmp_path/"profile"; home.mkdir()
    (home/"config.yaml").write_text("security:\n  untrusted_content_guard: true\n",encoding="utf-8")
    (home/".env").write_text("GEMINI_API_KEY=fixture-live-server-key\n",encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME",str(home))
    monkeypatch.setattr(profiles,"_get_profiles_root",lambda:tmp_path/"profiles")
    monkeypatch.setattr(profiles,"_get_default_hermes_home",lambda:home)
    monkeypatch.setitem(web_server.app.state._state,"bound_host","127.0.0.1")
    monkeypatch.setitem(web_server.app.state._state,"auth_required",False)
    monkeypatch.setattr(live,"limiter",live.SessionLimiter())
    monkeypatch.setattr(live,"SETUP_TIMEOUT",.4)
    monkeypatch.setattr(live,"SESSION_SECONDS",4)
    current = workspace(); current.shared_root = tmp_path/"shared"
    canary = current.canaries().create("fixture")
    with receiver() as upstream, TestClient(web_server.app,base_url="http://127.0.0.1") as client:
        monkeypatch.setattr(live,"LIVE_URL",upstream["url"])
        client.headers[web_server._SESSION_HEADER_NAME] = web_server._SESSION_TOKEN
        yield {"client":client,"upstream":upstream,"workspace":current,"canary":canary,"home":home,"root":tmp_path,"token":web_server._SESSION_TOKEN}


def url(env, **params):
    return "ws://127.0.0.1/api/indra/voice/live?"+urlencode({"model":MODEL,"token":env["token"],**params})


def ready(socket):
    socket.send_json(SETUP)
    receipt = socket.receive_json(); assert len(receipt["indraSession"]["id"]) == 32
    setup = socket.receive_json(); assert "setupComplete" in setup
    return receipt["indraSession"]["id"]


def wait_closed(env):
    assert env["upstream"]["closed"].wait(2)
    deadline = time.monotonic()+2
    while live.limiter.active and time.monotonic()<deadline: time.sleep(.01)
    assert not live.limiter.active


def test_real_audio_knowledge_frames_and_disconnect_cleanup(environment):
    env = environment
    with env["client"].websocket_connect(url(env)) as socket:
        session = ready(socket)
        audio = {"realtimeInput":{"audio":{"data":"AAA=","mimeType":"audio/pcm;rate=16000"}}}
        socket.send_json(audio)
        assert socket.receive_json()["serverContent"]["modelTurn"]["parts"][0]["inlineData"]["data"] == "AAA="
        result = {"toolResponse":{"functionResponses":[{"id":"call","name":"search_knowledge","response":{"result":{"context":"Six month interval","citations":[{"filename":"fixture.md"}]}}}]}}
        socket.send_json(result); assert socket.receive_json()["serverContent"]["turnComplete"]
        assert env["upstream"]["frames"] == [SETUP,audio,result]
        assert env["upstream"]["headers"] == ["fixture-live-server-key"]
    wait_closed(env)
    events = env["workspace"].audit.recent()
    ended_rows = [row for row in events if row["kind"] == "voice.live_ended"]
    assert len(ended_rows) == 1, {"kinds":[row["kind"] for row in events],"slots":len(live.limiter.active)}
    ended = ended_rows[0]
    assert ended["payload"]["session"] == session and ended["payload"]["sent_frames"] == 3
    # TestClient can cancel its ASGI task immediately after posting disconnect;
    # real ASGI servers normally deliver WebSocketDisconnect first. Both must
    # close the provider and preserve the completion receipt.
    assert ended["payload"]["outcome"] in {"client_disconnected","cancelled"}
    assert "Six month interval" not in json.dumps(events)
    assert "fixture-live-server-key" not in json.dumps(events)
    assert env["workspace"].audit.verify()["valid"]


@pytest.mark.parametrize("encoded", [False, True])
def test_knowledge_canary_never_reaches_upstream_and_stops_session(environment,encoded):
    import base64
    env = environment
    with env["client"].websocket_connect(url(env)) as socket:
        session = ready(socket)
        marker = env["canary"]["token"]
        if encoded: marker = base64.b64encode(marker.encode()).decode()
        socket.send_json({"toolResponse":{"functionResponses":[{"id":"call","name":"search_knowledge","response":{"result":marker}}]}})
        refused = socket.receive_json(); assert refused["error"]["code"] == "outbound_policy"
        with pytest.raises(WebSocketDisconnect) as error: socket.receive_json()
        assert error.value.code == 1008
    wait_closed(env)
    assert env["upstream"]["frames"] == [SETUP]
    incident = next(row for row in env["workspace"].audit.recent() if row["kind"] == "security.canary_blocked")
    assert incident["payload"]["session"] == session
    assert env["canary"]["id"] in incident["payload"]["canary_ids"]


def test_canary_setup_blocks_before_provider_connection(environment):
    env = environment
    with env["client"].websocket_connect(url(env)) as socket:
        setup = {"setup":{**SETUP["setup"],"systemInstruction":{"parts":[{"text":env["canary"]["token"]}]}}}
        socket.send_json(setup)
        assert socket.receive_json()["error"]["code"] == "outbound_policy"
    assert env["upstream"]["headers"] == [] and env["upstream"]["frames"] == []


def test_adjacent_text_fragments_cannot_export_complete_canary(environment):
    env = environment; token = env["canary"]["token"]
    with env["client"].websocket_connect(url(env)) as socket:
        ready(socket)
        socket.send_json({"realtimeInput":{"text":token[:25]}})
        assert socket.receive_json()["serverContent"]["turnComplete"]
        socket.send_json({"realtimeInput":{"text":token[25:]}})
        assert socket.receive_json()["error"]["code"] == "outbound_policy"
    wait_closed(env)
    assert len(env["upstream"]["frames"]) == 2


@pytest.mark.parametrize("params,headers,code", [({"token":"wrong"},{},4401),({"token":""},{},4401),
    ({},{"origin":"https://evil.example"},4403),({},{"host":"evil.example"},4403),({"model":"unsupported"},{},4400)])
def test_auth_origin_host_and_model_rejected_before_connection(environment,params,headers,code):
    env = environment
    with pytest.raises(WebSocketDisconnect) as error:
        with env["client"].websocket_connect(url(env,**params),headers=headers): pass
    assert error.value.code == code
    assert env["upstream"]["headers"] == []


def test_gated_ticket_is_single_use_and_legacy_token_rejected(environment,monkeypatch):
    from hermes_cli import web_server
    from hermes_cli.dashboard_auth.ws_tickets import mint_ticket
    env = environment; monkeypatch.setitem(web_server.app.state._state,"auth_required",True)
    with pytest.raises(WebSocketDisconnect):
        with env["client"].websocket_connect(url(env)): pass
    ticket = mint_ticket(user_id="fixture",provider="fixture")
    ticket_url = "ws://127.0.0.1/api/indra/voice/live?"+urlencode({"ticket":ticket,"model":MODEL})
    with env["client"].websocket_connect(ticket_url) as socket: ready(socket)
    wait_closed(env)
    with pytest.raises(WebSocketDisconnect):
        with env["client"].websocket_connect(ticket_url): pass
    assert len(env["upstream"]["headers"]) == 1


def test_provider_errors_never_echo_private_details(environment):
    env = environment
    with env["client"].websocket_connect(url(env)) as socket:
        ready(socket); socket.send_json({"realtimeInput":{"text":"provider-error"}})
        response = socket.receive_json()
        assert response["error"]["code"] == "provider_error"
        assert "fixture-live-server-key" not in json.dumps(response)
        assert "private-provider-detail" not in json.dumps(response)
    wait_closed(env)


def test_missing_key_and_invalid_profile_do_not_connect(environment):
    env = environment; (env["home"]/".env").write_text("")
    with env["client"].websocket_connect(url(env)) as socket:
        assert socket.receive_json()["error"]["code"] == "not_configured"
    with pytest.raises(WebSocketDisconnect):
        with env["client"].websocket_connect(url(env,profile="../../other")): pass
    assert env["upstream"]["headers"] == []


def test_direct_tokens_cannot_bypass_enabled_guard(environment):
    response = environment["client"].post("/api/indra/voice/token",json={"model":MODEL})
    assert response.status_code == 409
    assert "local Live voice bridge" in response.json()["detail"]


@pytest.mark.parametrize("raw", ['{bad','{"setup":{},"toolResponse":{}}','{"setup":{"model":"other"}}',
    '{"setup":{"model":"models/x","model":"models/y"}}','{"setup":{"model":NaN}}',"x"*(live.MAX_FRAME_CHARS+1)])
def test_malformed_setup_never_connects(environment,raw):
    env = environment
    with env["client"].websocket_connect(url(env)) as socket:
        socket.send_text(raw)
        assert socket.receive_json()["error"]["code"] == "voice_input"
    assert env["upstream"]["headers"] == []


def test_setup_timeout_releases_slot(environment):
    env = environment
    with env["client"].websocket_connect(url(env)) as socket:
        assert socket.receive_json()["error"]["code"] == "setup_timeout"
    assert not live.limiter.active and env["upstream"]["headers"] == []


def test_named_profile_uses_own_key_and_incident_log(environment):
    from hermes_cli.origo_workspace import workspace
    env = environment
    home = env["root"]/"profiles"/"reader"; home.mkdir(parents=True)
    (home/"config.yaml").write_text("security:\n  untrusted_content_guard: true\n")
    (home/".env").write_text("GEMINI_API_KEY=fixture-named-key\n")
    named = workspace(home); named.shared_root = env["root"]/"shared"
    with env["client"].websocket_connect(url(env,profile="reader")) as socket:
        ready(socket)
        assert env["upstream"]["headers"] == ["fixture-named-key"]
        socket.send_json({"realtimeInput":{"text":env["canary"]["token"]}})
        assert socket.receive_json()["error"]["code"] == "outbound_policy"
    wait_closed(env)
    assert any(r["kind"] == "security.canary_blocked" for r in named.audit.recent())
    assert not any(r["kind"] == "security.canary_blocked" for r in env["workspace"].audit.recent())
    assert named.audit.verify()["valid"]


def test_storage_failure_mid_stream_stops_the_next_frame(environment):
    env = environment
    with env["client"].websocket_connect(url(env)) as socket:
        ready(socket)
        env["workspace"].canaries().path.write_bytes(b"fixture corruption")
        socket.send_json({"realtimeInput":{"text":"Clean text with an unavailable registry"}})
        assert socket.receive_json()["error"]["code"] == "outbound_policy"
    wait_closed(env)
    assert env["upstream"]["frames"] == [SETUP]


def test_live_rotation_closes_upstream_and_preserves_resumption_payload(environment,monkeypatch):
    env = environment; monkeypatch.setattr(live,"SESSION_SECONDS",.1)
    with env["client"].websocket_connect(url(env)) as socket:
        ready(socket)
        with pytest.raises(WebSocketDisconnect) as error: socket.receive_json()
        assert error.value.code == 1012
    wait_closed(env)
    setup = {"setup":{**SETUP["setup"],"sessionResumption":{"handle":"fixture-resume"}}}
    with env["client"].websocket_connect(url(env)) as socket:
        socket.send_json(setup); assert "indraSession" in socket.receive_json()
        assert "setupComplete" in socket.receive_json()
        assert env["upstream"]["frames"][-1] == setup


def test_second_setup_and_oversize_frames_are_not_forwarded(environment):
    env = environment
    with env["client"].websocket_connect(url(env)) as socket:
        ready(socket); socket.send_json(SETUP)
        assert socket.receive_json()["error"]["code"] == "voice_input"
    wait_closed(env)
    assert env["upstream"]["frames"] == [SETUP]


def test_media_bytes_are_not_retained_in_rolling_text_window():
    frame = {"realtimeInput":{"audio":{"mimeType":"audio/pcm;rate=16000","data":"private-media"}}}
    assert live.text_tail(frame) == ""
    assert live.text_tail({"clientContent":{"turns":[{"parts":[{"text":"a"},{"text":"b"}]}]}}) == "ab"
    with pytest.raises(live.LiveFrameError): live.text_tail({"nested":[[]]*20_001})


def test_limiter_enforces_scope_and_releases_without_loop_binding():
    limit = live.SessionLimiter(total=2,per_profile=1,per_minute=2)
    first = limit.acquire("a")
    with pytest.raises(live.LiveFrameError): limit.acquire("a")
    second = limit.acquire("b")
    with pytest.raises(live.LiveFrameError): limit.acquire("c")
    limit.release(first); limit.release(second)
    third = limit.acquire("a"); limit.release(third)
    with pytest.raises(live.LiveFrameError): limit.acquire("a")
    assert not limit.active
