"""Pending/reconnected review cards obey the same scope as live notifications."""
from tui_gateway import server


def test_pending_rpc_normalizes_one_operation_choices(monkeypatch):
    from tools import approval
    session={"session_key":"fixture-chat","history":[]}
    monkeypatch.setattr(server,"_sessions",{"fixture-ui":session})
    pending=[{"request_id":"fixture-request","command":"<write_file>","allow_session":False,"allow_permanent":False}]
    monkeypatch.setattr(approval,"list_gateway_approvals",lambda key:pending)
    response=server.handle_request({"id":"fixture","method":"approval.pending","params":{"session_id":"fixture-ui"}})
    row=response["result"]["approvals"][0]
    assert row["choices"]==["once","deny"]
    assert row["request_id"]=="fixture-request"
    assert "choices" not in pending[0]


def test_closing_resumed_review_window_keeps_original_connection(monkeypatch):
    import threading
    original=object();reviewer=object()
    session={"session_key":"fixture-chat","transport":original,"history_lock":threading.Lock(),"close_on_disconnect":False}
    monkeypatch.setattr(server,"_sessions",{"fixture-ui":session})
    monkeypatch.setattr(server,"_transport_is_dead",lambda t:False)
    monkeypatch.setattr(server,"_schedule_ws_orphan_reap",lambda *a,**k:(_ for _ in ()).throw(AssertionError("original viewer is still connected")))
    server._attach_session_viewer(session,reviewer)
    assert original in session["viewers"] and reviewer in session["viewers"]
    assert server._close_sessions_for_transport(reviewer)==(0,0)
    assert session["transport"] is original
