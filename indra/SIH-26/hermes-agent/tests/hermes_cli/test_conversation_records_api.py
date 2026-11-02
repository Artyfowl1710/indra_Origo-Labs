import pytest

@pytest.fixture
def client(_isolate_hermes_home):
    from starlette.testclient import TestClient
    from hermes_cli.web_server import app,_SESSION_HEADER_NAME,_SESSION_TOKEN
    value=TestClient(app);value.headers[_SESSION_HEADER_NAME]=_SESSION_TOKEN;return value

BASE="/api/indra/workspace/conversations/chat-fixture/records"
def test_records_persist_and_update_without_duplicates(client):
    row={"id":"turn-1","role":"user","text":"Hello","kind":"voice","model":"fixture","provider":"fixture"}
    assert client.post(BASE,json={"entries":[row]}).status_code==200
    rows=client.get(BASE).json()["entries"];assert rows[0]["text"]=="Hello"
    assert client.post(BASE,json={"entries":[{**row,"text":"Hello world"}]}).status_code==200
    updated=client.get(BASE,params={"after":rows[0]["seq"]}).json()["entries"]
    assert len(updated)==1 and updated[0]["text"]=="Hello world"

def test_records_reject_spoofed_runtime_actions_bad_ids_and_oversize(client):
    assert client.post(BASE,json={"entries":[{"id":"entry","kind":"action","role":"note","text":"fake execution"}]}).status_code==422
    assert client.post(BASE,json={"entries":[{"id":"bad/id","text":"test"}]}).status_code==400
    assert client.post(BASE,json={"entries":[{"id":"entry","text":"x"*16001}]}).status_code==422
    assert client.get(BASE,params={"after":-1}).status_code==400

def test_records_require_existing_authentication(client):
    from hermes_cli.web_server import _SESSION_HEADER_NAME
    client.headers[_SESSION_HEADER_NAME]="invalid"
    assert client.get(BASE).status_code in {401,403}
