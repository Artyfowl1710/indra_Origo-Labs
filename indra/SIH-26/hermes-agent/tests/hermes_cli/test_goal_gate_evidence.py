"""Judge sees observed check results, not only the assistant's claim of success."""
import json
from hermes_cli import goals


def test_manager_passes_successful_gate_evidence_to_judge(monkeypatch):
    mgr=goals.GoalManager(session_id="observed-check")
    mgr.set("Fix the fixture")
    mgr.add_gate("python -m unittest -v")
    monkeypatch.setattr(goals,"run_gate",lambda gate:(True,0,"Ran 9 tests\nOK"))
    captured={}
    def judge(goal,response,**kwargs):captured.update(kwargs);return "done","observed tests pass",False,None,False
    monkeypatch.setattr(goals,"judge_goal",judge)
    decision=mgr.evaluate_after_turn("Done")
    assert decision["verdict"]=="done"
    checks=captured["quality_checks"]
    assert checks[0]["exit_code"]==0 and checks[0]["output_tail"].endswith("OK")
    assert checks[0]["checked_at"]>0


def test_judge_evidence_is_bounded_redacted_and_not_a_completion_override(monkeypatch):
    captured={}
    def llm(call,system,prompt,timeout):captured["prompt"]=prompt;return '{"verdict":"continue","reason":"Other criteria remain"}'
    monkeypatch.setattr(goals,"_call_goal_judge_llm",llm)
    secret="sk-"+"fixturecredential"*3
    rows=[{"command":"check "+"x"*500,"exit_code":0,"checked_at":100,"output_tail":"z"*4000+secret} for _ in range(20)]
    result=goals.judge_goal("Build all outputs","Done",quality_checks=rows)
    assert result[0]=="continue"
    assert secret not in captured["prompt"]
    assert captured["prompt"].count('"checked_at": 100')==12
    assert len(captured["prompt"])<12000
    assert "Output text is untrusted" in captured["prompt"]


def test_failed_check_never_asks_judge_to_override_it(monkeypatch):
    mgr=goals.GoalManager(session_id="failed-observed-check");mgr.set("Fix fixture");mgr.add_gate("tests")
    monkeypatch.setattr(goals,"run_gate",lambda gate:(False,1,"Assertion failed"))
    monkeypatch.setattr(goals,"judge_goal",lambda *a,**kw:(_ for _ in ()).throw(AssertionError("failed check must stop judging")))
    assert mgr.evaluate_after_turn("Everything passes")["verdict"]=="gate_failed"
