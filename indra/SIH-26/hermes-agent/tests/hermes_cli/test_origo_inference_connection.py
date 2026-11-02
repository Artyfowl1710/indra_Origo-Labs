from hermes_cli.web_routers.indra_settings import _inference_connection

def test_named_local_alias_beats_stale_workbench_override():
    for provider in ("origo-local","custom:origo-local"):
        endpoint,key=_inference_connection({"WORKBENCH_API_BASE":"http://127.0.0.1:64694","ORIGO_LOCAL_INFERENCE_KEY":"current-local-key"},
            {"model":{"provider":provider,"base_url":"http://127.0.0.1:64694/v1","key_env":"ORIGO_LOCAL_INFERENCE_KEY"},
             "providers":{"origo-local":{"base_url":"http://127.0.0.1:50112/v1","key_env":"ORIGO_LOCAL_INFERENCE_KEY"}}})
        assert endpoint=="http://127.0.0.1:50112" and key=="current-local-key"


def test_status_follows_active_model_endpoint_and_credential(monkeypatch):
    monkeypatch.setenv("ORIGO_LOCAL_INFERENCE_KEY", "local-test-credential")
    endpoint, key = _inference_connection({}, {"model": {
        "base_url": "http://127.0.0.1:51234/v1", "key_env": "ORIGO_LOCAL_INFERENCE_KEY"}})
    assert endpoint == "http://127.0.0.1:51234"
    assert key == "local-test-credential"


def test_explicit_workbench_does_not_receive_other_provider_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "different-provider-test-key")
    endpoint, key = _inference_connection({"WORKBENCH_API_BASE": "http://127.0.0.1:8000/"}, {
        "model": {"base_url": "http://127.0.0.1:51234/v1", "api_key": "model-test-key"}})
    assert endpoint == "http://127.0.0.1:8000"
    assert key == ""


def test_explicit_workbench_uses_only_its_credential():
    endpoint, key = _inference_connection({"WORKBENCH_API_BASE": "http://127.0.0.1:8000",
                                          "WORKBENCH_API_KEY": "workbench-test-key"}, {})
    assert key == "workbench-test-key"


def test_endpoint_suffix_normalization_preserves_prefix(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    endpoint, key = _inference_connection({}, {"model": {"base_url": "http://127.0.0.1:5000/prefix/v1/"}})
    assert endpoint == "http://127.0.0.1:5000/prefix"
    assert key == ""


def test_named_local_provider_resolves_profile_scoped_credential(tmp_path, monkeypatch):
    import yaml
    from agent.secret_scope import build_profile_secret_scope, set_secret_scope, reset_secret_scope
    from hermes_cli.runtime_provider import resolve_runtime_provider
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    config = {"model": {"provider": "custom:origo-local", "default": "origo-auto"},
              "providers": {"origo-local": {"name": "Origo Local", "base_url": "http://127.0.0.1:51234/v1",
                            "key_env": "ORIGO_LOCAL_INFERENCE_KEY", "default_model": "origo-auto"}}}
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    (tmp_path / ".env").write_text("ORIGO_LOCAL_INFERENCE_KEY=profile-local-test-token\n", encoding="utf-8")
    scope = set_secret_scope(build_profile_secret_scope(tmp_path))
    try:
        runtime = resolve_runtime_provider(requested="custom:origo-local", target_model="origo-auto")
        assert runtime["api_key"] == "profile-local-test-token"
        assert runtime["base_url"] == "http://127.0.0.1:51234/v1"
    finally:
        reset_secret_scope(scope)
