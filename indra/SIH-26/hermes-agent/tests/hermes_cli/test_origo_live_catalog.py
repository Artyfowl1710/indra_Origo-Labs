import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from hermes_cli import openrouter_catalog as catalog


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    catalog._memory.clear(); catalog._failed.clear(); catalog._indices.clear(); catalog._mtimes.clear()


def rows():
    return [{"id": "test/multimodal:free", "architecture": {"input_modalities": ["text", "image", "video"]},
             "pricing": {"prompt": "0", "completion": "0"}, "supported_parameters": ["tools"]},
            {"id": "test/multimodal", "pricing": {"prompt": ".01", "completion": ".02"}},
            {"id": "test/chat-only", "supported_parameters": []}]


def test_cache_and_force_refresh_have_distinct_behavior():
    calls = []
    def fetch(): calls.append(1); return rows()
    catalog.models(fetch); catalog.models(fetch)
    assert len(calls) == 1
    catalog.models(fetch, refresh=True)
    assert len(calls) == 2


def test_simultaneous_opens_fetch_once():
    calls = []
    def fetch(): calls.append(1); time.sleep(.02); return rows()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: catalog.models(fetch), range(8)))
    assert len(calls) == 1 and all(len(result) == 3 for result in results)


def test_offline_restart_reads_disk_and_retains_capabilities():
    catalog.models(rows); catalog._memory.clear()
    assert catalog.metadata("test/multimodal:free")["architecture"]["input_modalities"] == ["text", "image", "video"]
    assert catalog.models(lambda: None, refresh=True) == catalog.models()


def test_expired_cache_and_failed_refresh_do_not_hide_new_models(monkeypatch):
    catalog.models(rows)
    original = time.time()
    monkeypatch.setattr(catalog.time, "time", lambda: original + catalog.TTL + 1)
    assert len(catalog.models(lambda: None)) == 3
    assert len(catalog.models(lambda: rows() + [{"id": "test/new:free"}], refresh=True)) == 4


def test_very_stale_metadata_is_not_a_capability_verdict(monkeypatch):
    catalog.models(rows); original = time.time()
    monkeypatch.setattr(catalog.time, "time", lambda: original + catalog.STALE_TTL + 1)
    assert catalog.metadata("test/multimodal:free") is None


@pytest.mark.parametrize("bad", [None, {}, [], [None, {"id": 3}]])
def test_bad_refresh_preserves_good_snapshot(bad):
    catalog.models(rows)
    assert len(catalog.models(lambda: bad, refresh=True)) == 3


def test_cache_does_not_persist_credentials_or_mutable_aliases():
    result = catalog.models(lambda: [{**rows()[0], "api_key": "secret-fixture", "endpoint": "https://example.invalid"}])
    result[0]["id"] = "changed"
    assert catalog.metadata("test/multimodal:free") is not None
    assert "secret-fixture" not in catalog._path().read_text()


def test_picker_keeps_all_live_variants_and_models_without_tools(monkeypatch):
    import hermes_cli.models as m
    monkeypatch.setattr(m, "_fetch_live_catalog_index", lambda *a: (rows(), {}))
    monkeypatch.setattr("hermes_cli.model_catalog.get_curated_openrouter_models", lambda: [("old/curated", "")])
    ids = [mid for mid, _ in m.fetch_openrouter_models(force_refresh=True)]
    assert ids == [r["id"] for r in rows()]
    assert not m._openrouter_model_is_free({})
    assert m._openrouter_model_is_free({"prompt": "0", "completion": "0"})


def test_live_vision_metadata_overrides_older_catalog(monkeypatch):
    from agent.image_routing import _lookup_supports_vision
    catalog.models(rows)
    monkeypatch.setattr("agent.image_routing._probe_models_dev", lambda *a: False)
    assert _lookup_supports_vision("openrouter", "test/multimodal:free", {}) is True


def test_switch_drops_previous_endpoint_key_and_vision_override():
    from hermes_cli.web_server_config import _apply_main_model_assignment
    result = _apply_main_model_assignment({"provider": "custom:origo-local", "default": "origo-auto",
        "key_env": "ORIGO_LOCAL_INFERENCE_KEY", "supports_vision": True}, "openrouter", "test/chat-only")
    assert "key_env" not in result and "supports_vision" not in result


def test_runtime_key_provider_alias_is_canonicalized(tmp_path):
    import asyncio
    from hermes_cli.auth import read_credential_pool
    from hermes_cli.web_models import CredentialPoolAdd
    from hermes_cli.web_routers.ops import add_credential_pool_entry
    result = asyncio.run(add_credential_pool_entry(CredentialPoolAdd(provider="opencode.ai", api_key="fixture-key-not-real")))
    assert result["provider"] == "opencode-zen"
    assert read_credential_pool("opencode-zen")[0]["access_token"] == "fixture-key-not-real"
    assert not read_credential_pool("opencode.ai")


def test_free_provider_rejects_unused_key():
    import asyncio
    from fastapi import HTTPException
    from hermes_cli.web_models import CredentialPoolAdd
    from hermes_cli.web_routers.ops import add_credential_pool_entry
    with pytest.raises(HTTPException, match="anonymous"):
        asyncio.run(add_credential_pool_entry(CredentialPoolAdd(provider="opencode-free", api_key="fixture")))


@pytest.mark.parametrize("provider,message,reason", [
    ("opencode-free", "FreeUsageLimitError: Free models work in OpenCode", "provider_policy_blocked"),
    ("openrouter", "Rate limit exceeded: free-models-per-day", "rate_limit"),
])
def test_persistent_free_tier_rejection_does_not_retry_or_rotate(provider, message, reason):
    from agent.error_classifier import classify_api_error
    class Error(Exception): status_code = 429
    result = classify_api_error(Error(message), provider=provider)
    assert result.reason.value == reason
    assert not result.retryable and not result.should_rotate_credential


def test_chat_only_tools_decision_is_stable_and_changes_with_model(monkeypatch):
    from types import SimpleNamespace
    import agent.chat_completion_helpers as helper
    catalog.models(rows)
    monkeypatch.setattr(helper, "_reasoning_config_for_wire", lambda _: None)
    monkeypatch.setattr(helper, "effective_request_overrides", lambda _: {})
    monkeypatch.setattr(helper, "_prompt_cache_scope_for_agent", lambda _: "fixture")
    monkeypatch.setattr(helper, "_build_chat_completions_kwargs", lambda agent, messages, tools, *a: {"tools": tools})
    agent = SimpleNamespace(provider="openrouter", model="test/chat-only", api_mode="chat_completions", tools=[{"type": "function"}])
    assert helper._build_api_kwargs_for_mode(agent, [])['tools'] == []
    assert agent.tools == [{"type": "function"}]
    agent.model = "test/multimodal:free"
    assert helper._build_api_kwargs_for_mode(agent, [])['tools'] == agent.tools


def test_public_catalog_remains_browsable_without_usable_credentials(monkeypatch):
    from hermes_cli.inventory import ConfigContext, build_models_payload
    catalog.models(rows)
    monkeypatch.setattr("hermes_cli.model_switch.list_authenticated_providers", lambda **kw: [])
    monkeypatch.setattr("hermes_cli.inventory._local_runtime_row", lambda ctx: None)
    monkeypatch.setattr("hermes_cli.models.cached_provider_model_ids", lambda *a, **kw: [r['id'] for r in rows()])
    result = build_models_payload(ConfigContext('custom', 'fixture', '', {}, []), include_unconfigured=True, picker_hints=True)
    provider = next(p for p in result['providers'] if p['slug'] == 'openrouter')
    assert len(provider['models']) == 3
    assert provider['authenticated'] is False
    assert 'quota' in provider['warning']
