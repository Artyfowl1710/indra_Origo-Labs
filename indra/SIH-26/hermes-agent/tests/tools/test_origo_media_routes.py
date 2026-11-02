import pytest
from hermes_cli import openrouter_catalog as catalog
from agent.auxiliary_client import scoped_runtime_main
from tools.vision_tools import _video_route_kwargs


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr("tools.vision_tools._cfg_auxiliary", lambda *a, **kw: {})
    catalog._memory.clear(); catalog._indices.clear(); catalog._mtimes.clear()
    catalog.models(lambda: [
        {"id": "test/reader:free", "architecture": {"input_modalities": ["text", "image", "video"]}, "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "test/image-only", "architecture": {"input_modalities": ["text", "image"]}},
    ])


def test_video_uses_same_selected_multimodal_model():
    with scoped_runtime_main({"provider": "openrouter", "model": "test/reader:free"}):
        route = _video_route_kwargs(None)
    assert route["provider"] == "openrouter" and route["model"] == "test/reader:free"


def test_image_only_main_uses_free_video_reader_on_same_provider():
    with scoped_runtime_main({"provider": "openrouter", "model": "test/image-only"}):
        assert _video_route_kwargs(None)["model"] == "test/reader:free"


def test_explicit_nonvideo_model_is_not_silently_replaced():
    with scoped_runtime_main({"provider": "openrouter", "model": "test/reader:free"}):
        with pytest.raises(ValueError, match="required input/output modalities"):
            _video_route_kwargs("test/image-only")


def test_local_image_gateway_does_not_receive_video():
    with scoped_runtime_main({"provider": "custom", "model": "origo-auto"}):
        with pytest.raises(ValueError, match="supports images, not video"):
            _video_route_kwargs(None)


def test_explicit_video_endpoint_retains_its_own_key_scope(monkeypatch):
    monkeypatch.setattr("tools.vision_tools._cfg_auxiliary", lambda *a, **kw: {
        "provider": "custom", "model": "my-video-model", "base_url": "http://127.0.0.1:12345/v1", "key_env": "MY_VIDEO_KEY"})
    monkeypatch.setattr("agent.auxiliary_client._scoped_key_env", lambda name: "fixture-video-key" if name == "MY_VIDEO_KEY" else None)
    with scoped_runtime_main({"provider": "openrouter", "model": "test/reader:free", "api_key": "other-fixture-key"}):
        route = _video_route_kwargs(None)
    assert route["api_key"] == "fixture-video-key" and route["model"] == "my-video-model"


def test_aux_image_analysis_keeps_vision_capable_main(monkeypatch):
    import agent.auxiliary_client as aux
    monkeypatch.setattr(aux, "_resolve_provider_vision_default", lambda _: "other/default")
    monkeypatch.setattr("agent.image_routing._lookup_supports_vision", lambda *a: True)
    observed = []
    def client(provider, model, **kw): observed.append((provider, model)); return object(), model
    monkeypatch.setattr(aux, "resolve_provider_client", client)
    aux._vision_main_provider_client("openrouter", "test/reader:free", {}, None, None)
    assert observed == [("openrouter", "test/reader:free")]


def test_model_only_video_override_is_validated_before_capable_main(monkeypatch):
    monkeypatch.setattr("tools.vision_tools._cfg_auxiliary", lambda *a, **kw: {
        "model": "test/image-only"})
    with scoped_runtime_main({"provider": "openrouter", "model": "test/reader:free"}):
        with pytest.raises(ValueError, match="required input/output modalities"):
            _video_route_kwargs(None)


def test_auto_model_sentinel_keeps_primary(monkeypatch):
    monkeypatch.setattr("tools.vision_tools._cfg_auxiliary", lambda *a, **kw: {
        "provider": "auto", "model": "auto"})
    with scoped_runtime_main({"provider": "openrouter", "model": "test/reader:free"}):
        assert _video_route_kwargs("auto")["model"] == "test/reader:free"
