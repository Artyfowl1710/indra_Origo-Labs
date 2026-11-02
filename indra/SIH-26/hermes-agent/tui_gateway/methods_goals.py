"""Session-scoped goal editing and evidence; execution stays in the normal turn."""
from .method_ctx import HandlerRegistry,bind_module
_registry=HandlerRegistry()
method=_registry.method


def _goal_view(session):
    import json
    from hermes_cli import goals
    from hermes_cli.config import load_config
    with _profile_build_scope(session.get("profile_home")):
        state=goals.load_goal(session["session_key"])
        config=load_config()
    return {"state":json.loads(state.to_json()) if state and state.status!="cleared" else None,
            "session_id":session["session_key"],"running":bool(session.get("running")),
            "cwd":session.get("cwd") or "","execution_backend":(config.get("terminal") or {}).get("backend","local")}


@method("goal.get")
def _goal_get(rid,params):
    session,error=_sess_nowait(params,rid)
    if error:return error
    try:return _ok(rid,_goal_view(session))
    except Exception:return _err(rid,5007,"Goal storage is unavailable")


@method("goal.configure")
def _goal_configure(rid,params):
    session,error=_sess_nowait(params,rid)
    if error:return error
    if session.get("running"):return _err(rid,4019,"Pause the current run before editing its goal")
    from hermes_cli import goals
    import time
    try:
        text=params.get("objective","")
        if not isinstance(text,str) or not 1<=len(text.strip())<=12000:raise ValueError("Enter an objective under 12,000 characters")
        contract=params.get("contract") or {}
        if not isinstance(contract,dict) or any(k not in {"outcome","verification","constraints","boundaries","stop_when"} or not isinstance(v,str) or len(v)>8000 for k,v in contract.items()):raise ValueError("Invalid completion criteria")
        turns=params.get("max_turns",20)
        if type(turns) is not int or not 1<=turns<=200:raise ValueError("Choose a turn limit from 1 to 200")
        specs=params.get("gates",[])
        if not isinstance(specs,list) or len(specs)>12:raise ValueError("Choose up to 12 quality checks")
        gates=[]
        for spec in specs:
            if not isinstance(spec,dict):raise ValueError("Invalid quality check")
            command=spec.get("command","");timeout=spec.get("timeout_seconds",120);retries=spec.get("max_retries",2)
            if not isinstance(command,str) or not 1<=len(command.strip())<=2000 or "\0" in command:raise ValueError("Enter a check command under 2,000 characters")
            if type(timeout) is not int or not 1<=timeout<=300 or type(retries) is not int or not 0<=retries<=5:raise ValueError("Checks allow 1–300 seconds and 0–5 retries")
            gates.append(goals.GoalGate(command=command.strip(),timeout_seconds=timeout,max_retries=retries))
        with _profile_build_scope(session.get("profile_home")):
            old=goals.load_goal(session["session_key"])
            if old and old.status!="cleared" and params.get("expected_created_at")!=old.created_at:return _err(rid,4090,"The goal changed. Refresh before editing it.")
            if _ensure_session_db_row(session) is False:raise RuntimeError("Session storage unavailable")
            with _session_db(session) as db:
                if db is not None and not db.get_session_title(session["session_key"]):
                    db.set_session_title(session["session_key"],f"Goal · {text.strip()[:64]} · {session['session_key'][-6:]}")
            state=goals.GoalState(goal=text.strip(),status="paused",max_turns=turns,created_at=time.time(),
                                  contract=goals.GoalContract.from_dict(contract),gates=gates,paused_reason="Ready to start")
            goals.save_goal(session["session_key"],state)
            stored=goals.load_goal(session["session_key"])
            if not stored or stored.to_json()!=state.to_json():raise RuntimeError("Goal storage unavailable")
        return _ok(rid,_goal_view(session))
    except (ValueError,TypeError) as error:return _err(rid,4004,str(error))
    except Exception:return _err(rid,5007,"The goal could not be saved")


def register(server):
    bind_module(globals(),server)
