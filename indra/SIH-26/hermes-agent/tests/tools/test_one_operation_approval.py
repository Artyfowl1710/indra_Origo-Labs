"""The optional strong gate is fresh human consent, not an approval-cache lookup."""
import pytest
from tools import approval


@pytest.mark.parametrize("reply",["once","session","always"])
def test_strong_gate_ignores_yolo_cache_and_never_persists(monkeypatch,reply):
    prompts=[]
    def human(command,reason,**flags):prompts.append(flags);return reply
    monkeypatch.setattr(approval,"_presence",lambda cb=None:(human,True,False,False))
    monkeypatch.setattr(approval,"_yolo_active",lambda:True)
    monkeypatch.setattr(approval,"is_approved",lambda *a:True)
    monkeypatch.setattr(approval,"_persist_choice",lambda *a:pytest.fail("one-operation approval must never persist"))
    for _ in range(2):assert approval.request_tool_approval("send","untrusted read",require_human_once=True)["approved"]
    assert len(prompts)==2
    assert all(p["allow_permanent"] is False and p["allow_session"] is False for p in prompts)


@pytest.mark.parametrize("reply",["deny","timeout","invalid",None])
def test_strong_gate_denial_timeout_and_invalid_response_block(monkeypatch,reply):
    monkeypatch.setattr(approval,"_presence",lambda cb=None:(lambda *a,**k:reply,True,False,False))
    assert not approval.request_tool_approval("send","untrusted read",require_human_once=True)["approved"]


def test_strong_gate_unattended_autoapproval_cannot_replace_a_human(monkeypatch):
    monkeypatch.setattr(approval,"_presence",lambda cb=None:(None,False,False,False))
    monkeypatch.setattr(approval,"_yolo_active",lambda:True)
    monkeypatch.setattr(approval,"_unattended_contexts",lambda:pytest.fail("must not consult unattended approve modes"))
    assert not approval.request_tool_approval("send","untrusted read",require_human_once=True)["approved"]


def test_gateway_sees_only_once_or_deny(monkeypatch):
    monkeypatch.setattr(approval,"_presence",lambda cb=None:(None,False,True,False))
    monkeypatch.setattr(approval,"_gateway_notify_cb",lambda sid:object())
    notices=[]
    def answer(sid,callback,data,**kw):
        notices.append(data);return {"choice":"once","resolved":True}
    monkeypatch.setattr(approval,"_await_gateway_decision",answer)
    for _ in range(2):assert approval.request_tool_approval("send","untrusted read",require_human_once=True)["approved"]
    assert all(n["allow_session"] is False and n["allow_permanent"] is False for n in notices)
    assert notices[0]["pattern_keys"]!=notices[1]["pattern_keys"]


def test_directive_cannot_be_shadowed_or_change_arguments_after_review(monkeypatch):
    from hermes_cli import lifecycle,plugins
    strong={"action":"approve","message":"untrusted read","require_human_once":True}
    monkeypatch.setattr(lifecycle,"invoke_hook",lambda *a,**k:[{"action":"approve","message":"ordinary"},strong])
    directive=plugins._get_pre_tool_call_directive_details("send",{"to":"A"})
    assert directive.require_human_once
    monkeypatch.setattr(lifecycle,"invoke_hook",lambda *a,**k:[strong,{"action":"modify","args":{"to":"B"}}])
    assert plugins._get_pre_tool_call_directive_details("send",{"to":"A"}).action=="block"
    monkeypatch.setattr(lifecycle,"invoke_hook",lambda *a,**k:[strong,{"action":"block","message":"policy denied"}])
    assert plugins._get_pre_tool_call_directive_details("send",{}).action=="block"
