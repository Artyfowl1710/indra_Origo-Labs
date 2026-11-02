import base64
import concurrent.futures
import json
from unittest.mock import patch
import pytest

from hermes_cli import gemini_catalog as catalog
from hermes_cli import model_modalities as routing


@pytest.fixture
def cache(tmp_path, monkeypatch):
    path = tmp_path / "models.json"
    monkeypatch.setattr(catalog, "_path", lambda: path)
    catalog._memory.clear(); catalog._failures.clear()
    return path


def row(name="gemini-test"):
    return {"name": "models/" + name, "displayName": name, "supportedGenerationMethods": ["generateContent"]}


def test_cache_is_credential_scoped_and_secret_free(cache):
    calls = []
    def fetch(key, base): calls.append(key); return [row(key[-1])]
    a = catalog.models(api_key="secret-a", fetcher=fetch)
    assert catalog.models(api_key="secret-a", fetcher=fetch) == a
    assert len(calls) == 1
    assert catalog.models(api_key="secret-b", fetcher=fetch)[0]["id"] == "b"
    assert "secret" not in cache.read_text()
    a[0]["id"] = "mutated"
    assert catalog.cached_models()[0]["id"] == "b"


def test_stale_fallback_failure_backoff_and_rotation(cache):
    catalog.models(api_key="a", fetcher=lambda *args: [row()])
    data = json.loads(cache.read_text()); data["at"] -= catalog.TTL + 1
    cache.write_text(json.dumps(data)); catalog._memory.clear()
    calls = []
    def fail(*args): calls.append(1); raise OSError("offline")
    assert catalog.models(api_key="a", fetcher=fail)
    assert catalog.models(api_key="a", fetcher=fail)
    assert len(calls) == 1
    assert catalog.models(api_key="b", fetcher=fail) == []


def test_invalid_cache_and_bad_records(cache):
    cache.write_text("{broken")
    assert catalog.models(api_key="", fetcher=lambda *args: []) == []
    assert catalog.models(api_key="a", fetcher=lambda *args: [None, {"name": "bad\n"}, row()])[0]["id"] == "gemini-test"


def test_concurrent_refresh_is_single_flight(cache):
    calls = []
    def fetch(*args): calls.append(1); return [row()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: catalog.models(api_key="a", fetcher=fetch), range(12)))
    assert all(results) and len(calls) == 1


def test_native_pagination_and_header_auth(monkeypatch):
    from hermes_cli import urllib_security
    import io
    calls = []
    pages = [{"models": [row("a")], "nextPageToken": "next"}, {"models": [row("b")]}]
    def open_url(req, **kwargs):
        calls.append(req)
        return io.BytesIO(json.dumps(pages.pop(0)).encode())
    monkeypatch.setattr(urllib_security, "open_credentialed_url", open_url)
    assert len(catalog._fetch("private-key", catalog.BASE)) == 2
    assert "private-key" not in calls[0].full_url
    assert calls[0].get_header("X-goog-api-key") == "private-key"
    assert "pageToken=next" in calls[1].full_url


@pytest.mark.parametrize("payload", [{}, {"models": [] , "nextPageToken": 3}, {"models": [], "nextPageToken": "same"}])
def test_bad_pagination_fails(monkeypatch, payload):
    from hermes_cli import urllib_security
    import io
    monkeypatch.setattr(urllib_security, "open_credentialed_url", lambda *args, **kw: io.BytesIO(json.dumps(payload).encode()))
    with pytest.raises(ValueError): catalog._fetch("key", catalog.BASE)


def capable(mid, cost="0", media=("image", "video", "audio")):
    return {"id": mid, "input_modalities": ["text", *media], "output_modalities": ["text"], "chat_compatible": True, "prompt_price": cost, "completion_price": cost}


def test_main_then_explicit_then_cheapest_reader():
    options = [capable("paid", "0.2"), capable("free"), capable("unknown", None)]
    with patch.object(routing, "describe", side_effect=lambda p,m,c=None: next((v for v in options if v["id"] == m), {})), patch.object(routing, "candidates", return_value=options):
        assert routing.choose("openrouter", "paid", {"image"})["model"] == "paid"
        assert routing.choose("openrouter", "text-main", {"video"}, explicit_model="paid")["model"] == "paid"
        assert routing.choose("openrouter", "text-main", {"image", "video"})["model"] == "free"
        with pytest.raises(ValueError): routing.choose("openrouter", "text-main", {"image"}, explicit_model="text-main")


def test_unknown_price_not_free_and_image_reader_not_video():
    with patch.object(routing, "describe", return_value={}), patch.object(routing, "candidates", return_value=[capable("unknown", None), capable("image-only", "0", ("image",))]):
        with pytest.raises(ValueError): routing.choose("gemini", "text", {"video"})


def test_unavailable_models_are_scoped_to_credential_and_profile(_isolate_hermes_home):
    options = [capable("old", "0"), capable("next", "0.1")]
    with patch.object(routing, "describe", return_value={}), patch.object(routing, "candidates", return_value=options):
        routing.mark_unavailable("gemini", "old", "key-a")
        assert routing.choose("gemini", "text", {"image"}, scope="key-a")["model"] == "next"
        assert routing.choose("gemini", "text", {"image"}, scope="key-b")["model"] == "old"


def test_reader_404_recovery_stays_on_provider_and_preserves_explicit_selection(_isolate_hermes_home):
    from types import SimpleNamespace
    from agent import auxiliary_client as aux
    class NotFound(Exception): status_code = 404
    error = NotFound("Model not found")
    runtime = {"provider": "gemini", "model": "text-main", "api_key": "runtime-key", "base_url": catalog.BASE}
    route = SimpleNamespace(task="vision", tag="", resolved_provider="gemini", main_runtime=runtime,
                            resolved_model=None, final_model="old", route_info={})
    options = [capable("old", "0"), capable("next", "0.1")]
    with patch.object(routing, "describe", return_value={}), patch.object(routing, "candidates", return_value=options), patch.object(aux, "resolve_provider_client", return_value=(object(), "next")) as resolver:
        generator = aux._ladder_provider_fallback(error, route)
        step = next(generator)
        assert step.kind == "fallback" and step.args[1:] == ("next", "gemini")
        assert resolver.call_args.kwargs["explicit_api_key"] == "runtime-key"
        with pytest.raises(StopIteration) as completed: generator.send("response")
        assert completed.value.value == "response"
        route.resolved_model = "old"
        with pytest.raises(StopIteration): next(aux._ladder_provider_fallback(error, route))


def test_native_input_audio():
    from agent.gemini_native_adapter import _inline_data_part
    data = base64.b64encode(b"audio").decode()
    assert _inline_data_part({"type": "input_audio", "input_audio": {"data": data, "format": "wav"}})["inlineData"]["mimeType"] == "audio/wav"


@pytest.mark.parametrize("value", [None, "NaN", "Infinity", "-1", "bad"])
def test_invalid_prices(value): assert routing.price(value) is None


def test_google_specialists_are_visible_but_not_chat(cache):
    catalog.models(api_key="key", fetcher=lambda *args: [
        {"name": "models/test-tts", "displayName": "Test TTS", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/test-live", "supportedGenerationMethods": ["bidiGenerateContent"]},
        {"name": "models/test-embed", "supportedGenerationMethods": ["embedContent"]}])
    for name in ("test-tts", "test-live", "test-embed"):
        assert routing.describe("gemini", name)["chat_compatible"] is False


def test_native_catalog_is_not_hidden_by_an_old_generic_snapshot():
    from hermes_cli.models import cached_provider_model_ids
    with patch.object(catalog, "models", return_value=[{"id": "new-google-model"}]), patch("hermes_cli.models._load_provider_models_cache", side_effect=AssertionError("must not use old snapshot")):
        assert cached_provider_model_ids("gemini") == ["new-google-model"]


@pytest.mark.parametrize("kind,mime", [("image_url", "image/png"), ("video_url", "video/mp4"), ("audio_url", "audio/wav")])
def test_native_media_is_not_dropped(kind, mime):
    from agent.gemini_native_adapter import build_gemini_request
    data = base64.b64encode(b"test-media").decode()
    request = build_gemini_request(messages=[{"role": "user", "content": [{"type": kind, kind: {"url": f"data:{mime};base64,{data}"}}]}])
    assert request["contents"][0]["parts"][0]["inlineData"] == {"mimeType": mime, "data": data}


@pytest.mark.parametrize("url", ["https://example.test/private.png", "data:video/mp4;base64,YQ==", "data:image/png;base64,!!", "data:image/png;base64,"])
def test_invalid_media_is_reported(url):
    from agent.gemini_native_adapter import _inline_data_part, GeminiAPIError
    with pytest.raises(GeminiAPIError): _inline_data_part({"type": "image_url", "image_url": {"url": url}})


def test_self_hosted_explicit_capabilities():
    cfg = {"providers": {"my-server": {"models": {"local-vl": {"input_modalities": ["text", "image"], "output_modalities": ["text"]}}}}}
    assert routing.choose("my-server", "local-vl", {"image"}, config=cfg)["reason"] == "capable main model"


def test_live_google_key_survives_automatic_reader_switch(_isolate_hermes_home):
    from agent import auxiliary_client as aux
    runtime = {"provider": "gemini", "model": "text-only", "api_key": "runtime-key", "base_url": catalog.BASE}
    with patch.object(routing, "choose", return_value={"model": "gemini-test-reader"}):
        client, model = aux._vision_main_provider_client("gemini", "text-only", runtime, None, None)
    assert model == "gemini-test-reader"
    assert client.api_key == "runtime-key"
    assert client.base_url == catalog.BASE
    client.close()


def test_explicit_video_provider_reuses_only_matching_runtime_key(_isolate_hermes_home):
    from agent import auxiliary_client as aux
    runtime = {"provider": "gemini", "model": "gemini-test", "api_key": "runtime-key", "base_url": catalog.BASE}
    provider, client, model = aux.resolve_vision_provider_client(provider="gemini", model="gemini-test", main_runtime=runtime)
    assert provider == "gemini" and client.api_key == "runtime-key"
    client.close()
    with patch.object(aux, "_get_cached_client", return_value=(None, None)) as resolver:
        aux.resolve_vision_provider_client(provider="openai", model="test", main_runtime=runtime)
        assert "runtime-key" not in str(resolver.call_args)


@pytest.fixture
def client(_isolate_hermes_home):
    from starlette.testclient import TestClient
    from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN
    result = TestClient(app)
    result.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN
    return result


def test_key_provider_catalog_is_complete_and_keyless_excluded(client):
    from hermes_cli.provider_catalog import provider_catalog
    response = client.get("/api/providers/catalog")
    assert response.status_code == 200
    ids = {p["id"] for p in response.json()["providers"]}
    assert "gemini" in ids and "openrouter" in ids
    assert ids == {p.slug for p in provider_catalog() if p.auth_type == "api_key" and p.api_key_env_vars and not p.keyless}


def test_endpoint_optional_key_and_capabilities_round_trip(client):
    from hermes_cli.config import load_config_readonly
    body = {"name": "Test Local Server", "base_url": "http://127.0.0.1:11434/v1", "model": "test-vl", "input_modalities": ["text", "image"]}
    response = client.post("/api/providers/custom-endpoints", json=body)
    assert response.status_code == 200
    config = load_config_readonly()
    endpoint = next(v for v in config["providers"].values() if v.get("name") == body["name"])
    assert not endpoint.get("api_key") and not endpoint.get("key_env")
    assert endpoint["models"]["test-vl"]["supports_vision"] is True
    assert endpoint["models"]["test-vl"]["input_modalities"] == ["text", "image"]


@pytest.mark.parametrize("url", ["file:///C:/private", "https://key:secret@example.test/v1", "https://example.test/v1?key=secret", "https://example.test/v1#fragment"])
def test_endpoint_rejects_unsafe_url_shapes(client, url):
    response = client.post("/api/providers/custom-endpoints", json={"name": "invalid", "base_url": url, "model": "m"})
    assert response.status_code == 400


def test_routing_preview_is_read_only_and_redacts_credentials(client, monkeypatch):
    from hermes_cli.web_routers import models as routes
    from hermes_cli.config import save_config
    save_config({"model": {"provider": "gemini", "default": "test", "api_key": "sensitive"}})
    with patch.object(routing, "choose", return_value={"provider": "gemini", "model": "test", "reason": "capable main model"}):
        response = client.get("/api/model/media-routing")
    assert response.status_code == 200
    assert len(response.json()["routes"]) == 3
    assert "sensitive" not in response.text
