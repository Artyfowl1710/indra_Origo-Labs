"""Real backend goal-check acceptance; synthetic judge, no model/provider calls."""
from pathlib import Path
import json,os,sys,uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/"indra/SIH-26/hermes-agent"
sys.path.insert(0,str(CORE))
OUTPUT=ROOT/"data/test-results/goal-execution"
OUTPUT.mkdir(parents=True,exist_ok=True)
home=OUTPUT/"profile";home.mkdir(exist_ok=True)
project=OUTPUT/"project";project.mkdir(exist_ok=True)
os.environ["HERMES_HOME"]=str(home)

def main():
    from hermes_cli.goals import GoalManager,run_gate,GoalGate
    from hermes_constants import set_hermes_home_override,reset_hermes_home_override
    from tools.terminal_scope import terminal_scope,install_refusal_scope,reset_terminal_scope
    from tools.approval_context import set_current_session_key,reset_current_session_key
    from tools import terminal_tool as terminal
    from tools.terminal_tool_lifecycle import cleanup_vm
    task="goal-check-"+uuid.uuid4().hex[:10]
    policy={"TERMINAL_ENV":"docker","TERMINAL_DOCKER_IMAGE":"indra-documents:1","TERMINAL_CWD":str(project),
            "TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE":"true","TERMINAL_DOCKER_NETWORK":"false",
            "TERMINAL_CONTAINER_CPU":"1","TERMINAL_CONTAINER_MEMORY":"768",
            "TERMINAL_DOCKER_PERSIST_ACROSS_PROCESSES":"false","TERMINAL_CONTAINER_PERSISTENT":"false",
            "TERMINAL_DOCKER_ORPHAN_REAPER":"false"}
    token=set_hermes_home_override(str(home));approval=set_current_session_key(task)
    terminal.register_task_env_overrides(task,{"env_type":"docker","docker_image":"indra-documents:1","cwd":str(project),"cwd_source":"session"})
    rows=[]
    def check(name,value):
        rows.append({"name":name,"passed":bool(value)})
        if not value:raise AssertionError(name)
    try:
        with terminal_scope(policy):
            # A host Python process cannot resolve this container-only path.
            check("gate-runs-in-selected-container",run_gate(GoalGate(command='python -c "from pathlib import Path; print(Path(\'/opt/indra/smoke_indra_documents.py\').exists()); assert Path(\'/opt/indra/smoke_indra_documents.py\').is_file()"'))[0])
            (project/"answer.txt").write_text("broken",encoding="utf-8")
            mgr=GoalManager(task);mgr.set("Repair fixture and verify the result")
            mgr.add_gate('python -c "from pathlib import Path; import sys; value=Path(\'/workspace/answer.txt\').read_text(); print(value); sys.exit(0 if value==\'repaired\' else 3)"')
            with patch("hermes_cli.goals.judge_goal",return_value=("done","Synthetic fixture judge",False,None,False)) as judge:
                failed=mgr.evaluate_after_turn("Fixture still broken")
                check("failed-check-prevents-completion-and-skips-judge",failed["should_continue"] and failed["verdict"]=="gate_failed" and judge.call_count==0)
                (project/"answer.txt").write_text("repaired",encoding="utf-8")
                passed=mgr.evaluate_after_turn("Fixture repaired")
                check("changed-file-rechecked-and-success-can-complete",passed["status"]=="done" and mgr.state.gates[0].last_exit_code==0)
                check("check-output-survives-manager-reload","repaired" in GoalManager(task).state.gates[0].last_output_tail)
        marker=project/"HOST-FALLBACK-MUST-NOT-EXIST"
        refusal=install_refusal_scope("Synthetic unavailable selected backend")
        try:
            denied=run_gate(GoalGate(command=f'python -c "from pathlib import Path; Path(r\'{marker}\').touch()"'))
            check("unavailable-policy-does-not-fall-back-to-host",not denied[0] and not marker.exists())
        finally:reset_terminal_scope(refusal)
    finally:
        (OUTPUT/"acceptance.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
        cleanup_vm(task)
        terminal.clear_task_env_overrides(task)
        reset_current_session_key(approval);reset_hermes_home_override(token)
    print(json.dumps(rows))

if __name__=="__main__":main()
