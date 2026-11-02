import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

from hermes_state import SessionDB
from hermes_cli.usage_analytics import recorded_usage


@pytest.fixture
def client(_isolate_hermes_home):
    from starlette.testclient import TestClient
    from hermes_cli.web_server import app,_SESSION_HEADER_NAME,_SESSION_TOKEN
    value=TestClient(app);value.headers[_SESSION_HEADER_NAME]=_SESSION_TOKEN
    return value


@pytest.fixture
def db(_isolate_hermes_home):
    from hermes_constants import get_hermes_home
    value=SessionDB(get_hermes_home()/"state.db")
    yield value
    value.close()


def test_main_aux_models_daily_and_tasks_reconcile_once(client,db):
    db.create_session("mixed",source="cli",model="first")
    db.update_token_counts("mixed",model="first",billing_provider="custom",input_tokens=100,output_tokens=20,cache_read_tokens=30,cache_write_tokens=5,reasoning_tokens=10,estimated_cost_usd=.1,cost_status="estimated",api_call_count=1)
    db.update_token_counts("mixed",model="second",billing_provider="custom",input_tokens=200,output_tokens=40,cache_read_tokens=50,cache_write_tokens=10,reasoning_tokens=5,estimated_cost_usd=.2,cost_status="estimated",api_call_count=1)
    db.record_auxiliary_usage("mixed","vision",model="first",billing_provider="custom",input_tokens=500,output_tokens=100,cache_read_tokens=20,cache_write_tokens=2,reasoning_tokens=30,estimated_cost_usd=.4,cost_status="estimated",api_call_count=2)
    usage=client.get("/api/analytics/usage").json()
    models=client.get("/api/analytics/models").json()
    total=usage["totals"]
    assert total==models["totals"]
    assert (total["total_input"],total["total_output"],total["total_cache_read"],total["total_cache_write"],total["total_reasoning"])==(800,160,100,17,45)
    assert total["total_tokens"]==1077 and total["total_api_calls"]==4 and total["total_sessions"]==1
    assert total["total_estimated_cost"]==pytest.approx(.7)
    assert sum(row["total_tokens"] for row in usage["daily"])==1077
    assert sum(row["total_tokens"] for row in usage["by_task"])==1077
    assert sum(row["total_tokens"] for row in models["models"])==1077
    assert {row["model"]:row["input_tokens"] for row in models["models"]}=={"first":600,"second":200}
    assert usage["coverage"]["main_residual_sessions"]==0
    assert usage["coverage"]["not_invoice"] is True


def test_auxiliary_does_not_consume_main_summary_residual(db):
    db.create_session("legacy",source="cli",model="main")
    db.update_token_counts("legacy",model="main",input_tokens=100,output_tokens=10,api_call_count=1)
    db.record_auxiliary_usage("legacy","compression",model="aux",input_tokens=5000,output_tokens=500,api_call_count=1)
    db.update_token_counts("legacy",model="main",input_tokens=1000,output_tokens=100,api_call_count=3,absolute=True)
    report=recorded_usage(db,0)
    assert report["totals"]["total_input"]==6000
    assert report["totals"]["total_output"]==600
    assert report["totals"]["total_api_calls"]==4
    assert report["coverage"]["main_residual_sessions"]==1


def test_no_usage_completed_main_and_aux_calls_are_counted_but_not_priced(db):
    from agent.turn_usage import record_response_usage
    from agent.aux_accounting import set_accounting_context,reset_accounting_context,record_aux_usage
    db.create_session("missing",source="cli",model="main")
    agent=SimpleNamespace(_session_db=db,session_id="missing",_session_db_created=True,session_api_calls=0,
                          context_compressor=SimpleNamespace(awaiting_real_usage_after_compression=False),model="main",provider="custom",base_url="http://127.0.0.1:1/v1")
    response=SimpleNamespace(model="aux",usage=None)
    record_response_usage(agent,response,messages=[],api_call_count=1,api_duration=.1,compression_attempts=0,max_compression_attempts=1)
    token=set_accounting_context(db,"missing")
    try:record_aux_usage(response,"vision",provider="custom")
    finally:reset_accounting_context(token)
    assert db.flush_token_counts()
    report=recorded_usage(db,0)
    assert report["totals"]["total_api_calls"]==2
    assert report["totals"]["total_tokens"]==0
    assert report["totals"]["unknown_estimated_cost_rows"]==2
    assert report["totals"]["unknown_actual_cost_rows"]==2
    assert "127.0.0.1" not in json.dumps(report)


def test_session_summary_below_route_deltas_retains_detail(db):
    db.create_session("stale",source="cli",model="main")
    db.update_token_counts("stale",model="main",input_tokens=100,api_call_count=1)
    db.update_token_counts("stale",model="main",input_tokens=5,api_call_count=0,absolute=True)
    result=recorded_usage(db,0)
    assert result["totals"]["total_input"]==100
    assert result["coverage"]["summary_below_detail_sessions"]==1


def test_old_store_without_detail_uses_summary(db):
    db.create_session("old",source="cli",model="legacy")
    db.update_token_counts("old",model="legacy",input_tokens=10,output_tokens=2,api_call_count=1)
    with db._lock:db._conn.execute("DROP TABLE session_model_usage")
    result=recorded_usage(db,0)
    assert result["totals"]["total_tokens"]==12
    assert result["coverage"]["per_route_available"] is False


def test_named_profile_and_readonly_reporting_do_not_mix_state(client,db):
    from hermes_cli.profiles import create_profile
    db.create_session("default-only",source="cli",model="default-model")
    db.update_token_counts("default-only",model="default-model",input_tokens=100)
    home=create_profile("usage-only",no_alias=True,no_skills=True)
    other=SessionDB(home/"state.db")
    try:
        other.create_session("other-only",source="cli",model="other-model")
        other.update_token_counts("other-only",model="other-model",input_tokens=7,api_call_count=1)
    finally:other.close()
    path=home/"state.db";before=hashlib.sha256(path.read_bytes()).hexdigest()
    response=client.get("/api/analytics/usage?profile=usage-only")
    assert response.status_code==200
    assert response.json()["totals"]["total_input"]==7
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
    assert client.get("/api/analytics/usage").json()["totals"]["total_input"]==100
    assert client.get("/api/analytics/usage?days=0").status_code==422
    assert client.get("/api/analytics/usage?profile=../private").status_code in {400,404}
    from hermes_cli.web_server import _SESSION_HEADER_NAME
    client.headers[_SESSION_HEADER_NAME]="invalid"
    assert client.get("/api/analytics/usage").status_code in {401,403}


def test_real_agent_sdk_retry_and_auxiliary_response_feed_the_report(db):
    from run_agent import AIAgent
    from agent.auxiliary_client import call_llm
    from agent.aux_accounting import set_accounting_context,reset_accounting_context
    calls=[]
    class Receiver(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(body["model"])
            if len(calls)==1:
                status=429;reply={"error":{"message":"fixture retry","type":"rate_limit_error"}}
            else:
                status=200;reply={"id":"fixture-completion","object":"chat.completion","created":1,"model":body["model"],
                    "choices":[{"index":0,"message":{"role":"assistant","content":"Fixture answer."},"finish_reason":"stop"}],
                    "usage":{"prompt_tokens":100,"completion_tokens":20,"total_tokens":120,"prompt_tokens_details":{"cached_tokens":30}}}
            content_type="application/json"
            if status==200 and body.get("stream"):
                content_type="text/event-stream"
                common={"id":"fixture-completion","object":"chat.completion.chunk","created":1,"model":body["model"]}
                chunks=[{**common,"choices":[{"index":0,"delta":{"role":"assistant","content":"Fixture answer."},"finish_reason":None}]},
                        {**common,"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]},
                        {**common,"choices":[],"usage":reply["usage"]}]
                raw=("".join("data: "+json.dumps(chunk)+"\n\n" for chunk in chunks)+"data: [DONE]\n\n").encode()
            else:raw=json.dumps(reply).encode()
            self.send_response(status);self.send_header("Content-Type",content_type);self.send_header("Content-Length",str(len(raw)));self.send_header("Retry-After","0");self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(("127.0.0.1",0),Receiver)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f"http://127.0.0.1:{server.server_port}/v1";agent=None
    try:
        agent=AIAgent(provider="custom",model="fixture-main",base_url=base,api_key="synthetic-local-only",max_iterations=2,max_tokens=128,
                      enabled_toolsets=[],skip_context_files=True,skip_memory=True,skip_background_review=True,quiet_mode=True,
                      session_id="sdk-accounting",session_db=db,run_budget_seconds=20,reasoning_config={"enabled":False})
        result=agent.run_conversation("Reply with the fixture answer without tools.")
        assert result["final_response"]=="Fixture answer."
        token=set_accounting_context(db,"sdk-accounting")
        try:
            response=call_llm(task="compression",provider="custom",model="fixture-aux",base_url=base,api_key="synthetic-local-only",messages=[{"role":"user","content":"Summarize the synthetic fixture."}],max_tokens=64,timeout=5)
            assert response.choices[0].message.content=="Fixture answer."
        finally:reset_accounting_context(token)
        assert db.flush_token_counts()
        report=recorded_usage(db,0)
        assert {row["model"] for row in report["models"]} >= {"fixture-main","fixture-aux"}
        assert report["totals"]["total_tokens"]==240
        assert report["totals"]["total_cache_read"]==60
        assert report["totals"]["total_api_calls"]==2
        assert calls.count("fixture-main")>=2
        assert len(calls)>report["totals"]["total_api_calls"]
        assert "retries" in report["coverage"]["missing"]
    finally:
        if agent:agent.close()
        server.shutdown();server.server_close();thread.join(timeout=3)
