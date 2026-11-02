import pytest
from fastapi import HTTPException
from hermes_cli.phone_numbers import normalize_phone_allowlist
from hermes_cli.web_models import WhatsAppOnboardingStart
from hermes_cli.web_routers.messaging import _normalize_whatsapp_allowed_users


@pytest.mark.parametrize("number", ["9876543210", "09876543210", "+91 98765-43210",
                                     "00919876543210", "९८७६५४३२१०"])
def test_indian_owner_numbers_normalize_to_the_same_international_identity(number):
    assert normalize_phone_allowlist(number, "IN") == "919876543210"


def test_multiple_owners_are_deduplicated_and_foreign_country_codes_preserved():
    assert normalize_phone_allowlist("9876543210,+91 9876543210,+1 (202) 555-0123", "IN") == "919876543210,12025550123"


def test_platform_lid_identifiers_are_not_reinterpreted_as_indian_phones():
    assert normalize_phone_allowlist("9876543210@lid", "IN") == "9876543210@lid"
    assert normalize_phone_allowlist("", "IN") == ""
    assert normalize_phone_allowlist("12025550123", "international") == "12025550123"


@pytest.mark.parametrize("number", ["12345", "1234567890", "+91abc9876543210", "../credentials", "+91+9876543210"])
def test_invalid_owner_input_fails_before_pairing(number):
    with pytest.raises(HTTPException) as exc:
        _normalize_whatsapp_allowed_users(number, "IN")
    assert exc.value.status_code == 400


def test_region_contract_and_limits():
    assert WhatsAppOnboardingStart(default_country="IN").default_country == "IN"
    with pytest.raises(ValueError):
        normalize_phone_allowlist("9876543210", "unsupported")
    with pytest.raises(ValueError):
        normalize_phone_allowlist(",".join(["9876543210"] * 33), "IN")
