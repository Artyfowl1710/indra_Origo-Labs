"""Product content policy, using generic lifecycle and approval contracts."""
import json


def _guard():
    from hermes_cli.config import load_config_readonly
    if (load_config_readonly().get("security") or {}).get("untrusted_content_guard") is not True:return None
    from hermes_cli.origo_workspace import workspace
    return workspace().content_guard()


def before_turn(session_id="",turn_id="",user_message="",conversation_history=None,**kwargs):
    guard=_guard()
    if guard:
        from origo_runtime.content_guard import contains_evidence
        if contains_evidence(user_message,conversation_history):guard.mark(session_id,turn_id,"untrusted evidence in current context")


def observe_request(session_id="",turn_id="",user_message="",request_messages=None,**kwargs):
    # This observer marks input exposure; its return value does NOT block API
    # transmission. Outbound canary enforcement needs a separate veto contract.
    guard=_guard()
    if guard:
        from origo_runtime.content_guard import contains_evidence
        if contains_evidence(user_message,request_messages):guard.mark(session_id,turn_id,"untrusted text or media in model request")


def before_tool(tool_name,args=None,session_id="",turn_id="",tool_call_id="",**kwargs):
    try:
        guard=_guard()
        if guard:
            from hermes_cli.origo_workspace import workspace
            current=workspace()
            blocked=current.canaries().veto(args or {},current.audit,channel="tool",session=session_id,turn=turn_id)
            if blocked:return blocked
            return guard.before_tool(tool_name,args or {},session_id,turn_id,tool_call_id)
    except Exception:
        return {"action":"block","message":"Content-trust policy is unavailable. This operation has been stopped; inspect Runtime diagnostics."}


def before_model(request,session_id="",turn_id="",**context):
    # This is a veto contract; unlike the observer it is enforced before dispatch.
    try:
        if not _guard():return None
        from hermes_cli.origo_workspace import workspace
        current=workspace()
        return current.canaries().veto({"request":request,"route":context},current.audit,
            channel="model",session=session_id,turn=turn_id)
    except Exception:
        return {"action":"block","message":"Outbound canary policy unavailable."}


def screen_result(tool_name,result,session_id="",turn_id="",**kwargs):
    try:
        guard=_guard()
        if guard:return guard.screen_result(tool_name,result,session_id,turn_id)
    except Exception:
        return json.dumps({"error":"Tool content withheld because the content scanner is unavailable."})


def review_answer(pattern_key="",choice="",session_id="",turn_id="",**kwargs):
    if not str(pattern_key).startswith("plugin_rule:untrusted:"):return
    guard=_guard()
    if guard:
        guard.audit.append("security.human_review_answered",{"session":session_id,"turn":turn_id,
            "choice":"once" if choice in {"once","session","always"} else str(choice)[:40],
            "rule":str(pattern_key)[:240]})


def register(ctx):
    ctx.register_hook("pre_llm_call",before_turn)
    ctx.register_hook("pre_api_request",observe_request)
    ctx.register_hook("pre_model_request",before_model)
    ctx.register_hook("pre_tool_call",before_tool)
    ctx.register_hook("transform_tool_result",screen_result)
    ctx.register_hook("post_approval_response",review_answer)
