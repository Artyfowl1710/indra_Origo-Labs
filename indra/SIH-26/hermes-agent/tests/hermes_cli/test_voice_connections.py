import base64,json,httpx,pytest
from hermes_cli.web_routers import indra_voice

@pytest.fixture
def client(_isolate_hermes_home):
    from starlette.testclient import TestClient
    from hermes_cli.web_server import app,_SESSION_HEADER_NAME,_SESSION_TOKEN
    value=TestClient(app);value.headers[_SESSION_HEADER_NAME]=_SESSION_TOKEN;return value

@pytest.fixture
def baseten(monkeypatch):
    from hermes_cli import voice_connections
    cfg={"providers":{"baseten":{"voice_enabled":True,"base_url":"https://inference.baseten.co/v1","model":"meta-models/muse-spark-open-1026","api_key":"fixture-baseten-key","models":{"meta-models/muse-spark-open-1026":{"input_modalities":["text","audio"]}}}}}
    monkeypatch.setattr(voice_connections,"load_config",lambda:cfg)
    return cfg

def test_only_enabled_named_connections_are_offered(baseten):
    from hermes_cli.voice_connections import connections,resolve
    rows=connections();assert rows[0]["transport"]=="chat-speech"
    assert resolve(rows[0]["provider"],rows[0]["model"])[0]=="https://inference.baseten.co/v1"
    baseten["providers"]["baseten"]["voice_enabled"]=False
    assert connections()==[]
    with pytest.raises(ValueError):resolve("custom:baseten","meta-models/muse-spark-open-1026")

def test_baseten_turn_uses_declared_model_and_profile_knowledge(client,baseten,monkeypatch):
    sent=[]
    class FakeClient:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):sent.append((url,kwargs));return httpx.Response(200,json={"choices":[{"message":{"content":"Synthetic voice response"}}]})
    monkeypatch.setattr(indra_voice.httpx,"AsyncClient",FakeClient)
    response=client.post("/api/indra/voice/turn",json={"provider":"custom:baseten","model":"meta-models/muse-spark-open-1026","text":"Hello"})
    assert response.status_code==200
    assert response.json()["text"]=="Synthetic voice response"
    assert sent[0][0]=="https://inference.baseten.co/v1/chat/completions"
    assert sent[0][1]["headers"]["Authorization"]=="Bearer fixture-baseten-key"
    assert client.post("/api/indra/voice/turn",json={"provider":"custom:missing","model":"unknown","text":"Hello"}).status_code==400

def test_baseten_can_transcribe_native_audio_without_google_key(client,baseten,monkeypatch):
    monkeypatch.setattr(indra_voice,"credentials",lambda request:("fixture",""))
    sent=[]
    class FakeClient:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):sent.append(kwargs);return httpx.Response(200,json={"choices":[{"message":{"content":"Hello from voice"}}]})
    monkeypatch.setattr(indra_voice.httpx,"AsyncClient",FakeClient)
    response=client.post("/api/indra/voice/transcribe",json={"provider":"custom:baseten","model":"meta-models/muse-spark-open-1026","data_url":"data:audio/wav;base64,"+base64.b64encode(b"fixture-audio").decode()})
    assert response.status_code==200 and response.json()["transcript"]=="Hello from voice"
    assert sent[0]["json"]["messages"][0]["content"][1]["type"]=="audio_url"

def test_plain_http_remote_credentials_and_unlisted_models_are_rejected(baseten):
    from hermes_cli.voice_connections import resolve
    with pytest.raises(ValueError):resolve("custom:baseten","unlisted-model")
    baseten["providers"]["baseten"]["base_url"]="http://inference.baseten.co/v1"
    with pytest.raises(ValueError):resolve("custom:baseten","meta-models/muse-spark-open-1026")

def test_voice_opt_in_survives_legacy_endpoint_edits_and_can_be_disabled(_isolate_hermes_home):
    from hermes_cli.web_routers.config_env import _write_custom_endpoint
    from hermes_cli.web_models import CustomEndpointUpdate
    cfg={"providers":{}}
    fields={"name":"Baseten","base_url":"https://inference.baseten.co/v1","model":"meta-models/muse-spark-open-1026"}
    key,entry=_write_custom_endpoint(cfg,CustomEndpointUpdate(**fields,voice_enabled=True))
    assert entry["voice_enabled"] is True
    _,entry=_write_custom_endpoint(cfg,CustomEndpointUpdate(**fields))
    assert entry["voice_enabled"] is True
    _,entry=_write_custom_endpoint(cfg,CustomEndpointUpdate(**fields,voice_enabled=False))
    assert entry["voice_enabled"] is False
