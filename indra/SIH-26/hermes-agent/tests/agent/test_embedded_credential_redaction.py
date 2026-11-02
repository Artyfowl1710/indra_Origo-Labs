import pytest
from agent.redact import redact_sensitive_text


@pytest.mark.parametrize("token",["sk-"+"a"*32,"ghp_"+"b"*32,"AIza"+"c"*35])
def test_strict_evidence_redaction_masks_concatenated_tokens(token):
    assert token not in redact_sensitive_text("noise"+token,force=True,embedded_credentials=True)


def test_strict_evidence_redaction_handles_zero_width_splits():
    token="sk-"+"a"*16+"\u200b"+"b"*16
    result=redact_sensitive_text("noise"+token,force=True,embedded_credentials=True)
    assert token not in result and token.replace("\u200b","") not in result


def test_default_code_redaction_keeps_identifier_boundaries():
    identifier="mask-abcdefghijklmnop"
    assert redact_sensitive_text(identifier,force=True,code_file=True)==identifier
