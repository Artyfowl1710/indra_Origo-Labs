"""Consistent recorded-usage views over the existing session accounting store.

Route deltas are authoritative; only positive MAIN-session residuals are added.
Auxiliary usage never reduces the main residual. No prompts or endpoint URLs are
returned. Historical daily attribution follows the conversation's start date.
"""
from collections import defaultdict
from datetime import datetime, timezone
import sqlite3

COUNTERS=("input_tokens","output_tokens","cache_read_tokens","cache_write_tokens","reasoning_tokens","api_call_count")
SUMS=COUNTERS+("estimated_cost_usd","actual_cost_usd")


def recorded_usage(db, cutoff):
    connection=db._conn
    owned=not connection.in_transaction
    if owned:connection.execute("BEGIN")
    try:
        fields="id,model,billing_provider,started_at,tool_call_count,cost_status,"+",".join(SUMS)
        sessions=[dict(row) for row in connection.execute("SELECT "+fields+" FROM sessions WHERE started_at>?",(cutoff,))]
        try:
            fields="u.session_id,u.model,u.billing_provider,u.task,u.cost_status,"+",".join("u."+key for key in SUMS)
            detailed=[dict(row) for row in connection.execute("SELECT "+fields+" FROM session_model_usage u JOIN sessions s ON s.id=u.session_id WHERE s.started_at>?",(cutoff,))]
            detail_available=True
        except sqlite3.OperationalError:
            # Older read-only stores can lack per-route/task accounting entirely.
            if connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='session_model_usage'").fetchone():
                columns={row[1] for row in connection.execute("PRAGMA table_info(session_model_usage)")}
                if {"session_id","model","billing_provider","task",*SUMS,"cost_status"}.issubset(columns):raise
            detailed=[];detail_available=False
    finally:
        if owned:connection.execute("ROLLBACK")
    session_by_id={row["id"]:row for row in sessions}
    main_totals=defaultdict(lambda:dict.fromkeys(SUMS,0))
    for row in detailed:
        if not row["task"]:
            for key in SUMS:main_totals[row["session_id"]][key]+=row.get(key) or 0
    rows=detailed[:];residual_sessions=0;inconsistent=0
    detailed_sessions={row["session_id"] for row in detailed}
    for session in sessions:
        accounted=main_totals[session["id"]]
        residual={key:max(0,(session.get(key) or 0)-accounted[key]) for key in SUMS}
        if any(accounted[key]>(session.get(key) or 0) for key in COUNTERS):inconsistent+=1
        if any(residual.values()):
            rows.append({**session,**residual,"session_id":session["id"],"task":""})
            residual_sessions+=1
        elif session["id"] not in detailed_sessions and session.get("model"):
            # Keep idle sessions visible without inventing usage or spend.
            rows.append({**session,"session_id":session["id"],"task":""})
    def bucket():
        return {**dict.fromkeys(SUMS,0),"sessions":set(),"tool_calls":0,"last_used_at":0,
                "unknown_estimated_cost_rows":0,"unknown_actual_cost_rows":0}
    models=defaultdict(bucket);daily=defaultdict(bucket);tasks=defaultdict(bucket)
    unknown_estimates=unknown_actual=0
    for row in rows:
        session=session_by_id[row["session_id"]]
        day=datetime.fromtimestamp(session["started_at"],timezone.utc).date().isoformat()
        model=row.get("model") or "unknown";provider=row.get("billing_provider") or ""
        active=bool(any(row.get(key) for key in SUMS))
        estimate_known=row.get("cost_status") in {"estimated","included","free","actual","billed"} or (row.get("cost_status") is None and bool(row.get("estimated_cost_usd")))
        actual_known=row.get("cost_status") in {"actual","billed"} or bool(row.get("actual_cost_usd"))
        missing_estimate=int(active and not estimate_known);missing_actual=int(active and not actual_known)
        unknown_estimates+=missing_estimate;unknown_actual+=missing_actual
        for target in (models[(model,provider)],daily[day],tasks[row.get("task") or "main"]):
            for key in SUMS:target[key]+=row.get(key) or 0
            target["sessions"].add(session["id"])
            target["last_used_at"]=max(target["last_used_at"],session["started_at"])
            target["unknown_estimated_cost_rows"]+=missing_estimate
            target["unknown_actual_cost_rows"]+=missing_actual
    for session in sessions:
        key=(session.get("model") or "unknown",session.get("billing_provider") or "")
        if key in models:models[key]["tool_calls"]+=session.get("tool_call_count") or 0
    def finish(value):
        result={**value,"sessions":len(value["sessions"]),"api_calls":value["api_call_count"],
                "estimated_cost":value["estimated_cost_usd"],"actual_cost":value["actual_cost_usd"]}
        result["total_tokens"]=sum(result[key] for key in ("input_tokens","output_tokens","cache_read_tokens","cache_write_tokens"))
        result["avg_tokens_per_session"]=result["total_tokens"]/max(1,result["sessions"])
        return result
    model_rows=[{"model":model,"provider":provider,**finish(value)} for (model,provider),value in models.items()]
    model_rows.sort(key=lambda row:row["total_tokens"],reverse=True)
    totals={"total_"+key:sum(row[key] for row in model_rows) for key in ("input_tokens","output_tokens","cache_read_tokens","cache_write_tokens","reasoning_tokens")}
    totals={key.removesuffix("_tokens"):value for key,value in totals.items()}
    totals.update(total_tokens=sum(row["total_tokens"] for row in model_rows),total_api_calls=sum(row["api_calls"] for row in model_rows),
                  total_estimated_cost=sum(row["estimated_cost"] for row in model_rows),total_actual_cost=sum(row["actual_cost"] for row in model_rows),
                  total_sessions=len(sessions),distinct_models=len({row["model"] for row in model_rows}),
                  unknown_estimated_cost_rows=unknown_estimates,unknown_actual_cost_rows=unknown_actual)
    return {"models":model_rows,"totals":totals,"daily":[{"day":day,**finish(value)} for day,value in sorted(daily.items())],
            "by_model":model_rows,"by_task":[{"task":task,**finish(value)} for task,value in sorted(tasks.items())],
            "coverage":{"basis":"Recorded provider-response usage and positive main-session residuals; auxiliary rows included once.",
                        "daily_basis":"Conversation start date (UTC), not the individual request date.",
                        "cache_basis":"Input excludes cache reads/writes. Total includes those buckets; reasoning is a subset of output.",
                        "not_invoice":True,"per_route_available":detail_available,"main_residual_sessions":residual_sessions,
                        "summary_below_detail_sessions":inconsistent,
                        "missing":"Failed requests, hidden SDK/provider retries, responses without reported usage, and unrecorded media/service calls can have unknown tokens or spend."}}
