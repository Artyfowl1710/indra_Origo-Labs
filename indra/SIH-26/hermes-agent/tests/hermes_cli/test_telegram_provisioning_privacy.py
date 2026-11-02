import pytest
from fastapi import HTTPException
from hermes_cli.web_server_messaging import _telegram_onboarding_request_sync


def test_external_provisioning_is_opt_in_and_does_not_contact_the_old_host(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ONBOARDING_URL", raising=False)
    called = []
    monkeypatch.setattr("httpx.Client.request", lambda *a, **k: called.append(True))
    with pytest.raises(HTTPException) as error:
        _telegram_onboarding_request_sync("POST", "/v1/telegram/pairings")
    assert error.value.status_code == 503
    assert "BotFather" in error.value.detail
    assert called == []
