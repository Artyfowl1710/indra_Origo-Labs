import pytest,httpx
from hermes_cli.web_routers import indra_voice as voice
BASE="/api/indra/voice"

@pytest.fixture
def client(_isolate_hermes_home):
    from starlette.testclient import TestClient
    from hermes_cli.web_server import app,_SESSION_HEADER_NAME,_SESSION_TOKEN
    value=TestClient(app);value.headers[_SESSION_HEADER_NAME]=_SESSION_TOKEN
    return value

@pytest.fixture(autouse=True)
def reset_limits():
    voice._issued.clear()
    voice._speech_models.clear()
    yield
    voice._issued.clear()
    voice._speech_models.clear()

def test_voice_requires_the_existing_session_token(client):
    from hermes_cli.web_server import _SESSION_HEADER_NAME
    client.headers[_SESSION_HEADER_NAME]="invalid"
    assert client.get(BASE+"/status").status_code in {401,403}

def test_missing_google_key_has_actionable_status(client,monkeypatch):
    monkeypatch.setattr(voice,"credentials",lambda request:("fixture",""))
    assert client.get(BASE+"/status").json()["configured"] is False
    assert client.post(BASE+"/token",json={}).status_code==409
    assert client.post(BASE+"/token",json={"model":"file:///bad"}).status_code==400

def test_live_token_never_returns_permanent_key_and_is_rate_limited(client,monkeypatch):
    monkeypatch.setattr(voice,"credentials",lambda request:("fixture","permanent-secret-fixture"))
    from hermes_cli.origo_workspace import workspace
    from hermes_constants import get_hermes_home
    monkeypatch.setattr(voice,"credentials",lambda request:(str(get_hermes_home()),"permanent-secret-fixture"))
    sent=[]
    class FakeClient:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            sent.append((url,kwargs));return httpx.Response(200,json={"name":"short-lived-token"})
    monkeypatch.setattr(voice.httpx,"AsyncClient",FakeClient)
    for _ in range(4):
        result=client.post(BASE+"/token",json={})
        assert result.status_code==200
        assert result.json()["token"]=="short-lived-token"
        assert "permanent-secret-fixture" not in result.text
    assert sent[0][1]["json"]["uses"]==1
    assert sent[0][1]["headers"]["x-goog-api-key"]=="permanent-secret-fixture"
    assert client.post(BASE+"/token",json={}).status_code==429

def test_google_transcription_rejects_unsupported_and_oversize_audio(client,monkeypatch):
    monkeypatch.setattr(voice,"credentials",lambda request:("fixture","secret"))
    for value in ["not audio","data:text/plain;base64,YWJj","data:audio/wav;base64,%%%","data:audio/wav;base64,"+"A"*(12*1024*1024+1)]:
        assert client.post(BASE+"/transcribe",json={"data_url":value}).status_code==400

def test_transcription_uses_account_catalog_and_caches_model_selection(client,monkeypatch):
    import base64
    monkeypatch.setattr(voice,"credentials",lambda request:("fixture","test-key"))
    calls=[]
    class FakeClient:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def get(self,url,**kwargs):
            calls.append("catalog")
            return httpx.Response(200,json={"models":[{"name":"models/gemini-3.5-flash-lite","supportedGenerationMethods":["generateContent"]}]})
        async def post(self,url,**kwargs):
            calls.append(url)
            return httpx.Response(200,json={"candidates":[{"content":{"parts":[{"text":"private thought","thought":True},{"text":"Synthetic speech"}]}}]})
    monkeypatch.setattr(voice.httpx,"AsyncClient",FakeClient)
    for _ in range(2):
        result=client.post(BASE+"/transcribe",json={"data_url":"data:audio/wav;base64,"+base64.b64encode(b"synthetic-audio").decode()})
        assert result.status_code==200
        assert result.json()["model"]=="gemini-3.5-flash-lite"
        assert result.json()["transcript"]=="Synthetic speech"
    assert calls.count("catalog")==1
