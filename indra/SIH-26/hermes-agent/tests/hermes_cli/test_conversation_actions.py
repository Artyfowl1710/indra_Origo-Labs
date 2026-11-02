import json
from types import SimpleNamespace


def test_runtime_actions_bind_to_stored_chat_and_redact_known_credentials(tmp_path,monkeypatch):
    from hermes_cli import origo_workspace
    signed=[]
    current=SimpleNamespace(root=tmp_path,audit=SimpleNamespace(append=lambda event,data:signed.append((event,data))))
    monkeypatch.setattr(origo_workspace,"workspace",lambda home:current)
    # workspace normally installs the local package bridge before recording.
    import sys
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[5]))
    from origo_runtime.conversation_records import ConversationRecords
    token="sk-"+"a"*30
    payload={"name":"terminal","args":{"command":"echo "+token,"path":"project/demo.txt","unrelated":"private content"}}
    session={"session_key":"stable-chat","agent":SimpleNamespace(model="fixture-model",provider="fixture")}
    origo_workspace.record_event("tool.start","ephemeral-runtime",payload,session)
    rows=ConversationRecords(tmp_path).list("stable-chat")
    assert len(rows)==1 and rows[0]["source"]=="runtime"
    assert "terminal" in rows[0]["text"] and "demo.txt" in rows[0]["text"]
    assert token not in rows[0]["text"] and "private content" not in rows[0]["text"]
    assert rows[0]["model"]=="fixture-model"
    assert token not in json.dumps(signed) and "payload_hash" in signed[0][1]
    assert ConversationRecords(tmp_path).list("ephemeral-runtime")==[]
