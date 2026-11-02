import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.store import Store


class FakeAgent:
    def __init__(self):
        self.last_context = None
    async def run(self, message, history=None, event_sink=None, stream=False, context=None, mode="build", permission_requester=None, **kwargs):
        self.last_context = context
        if event_sink:
            event_sink({"type": "token", "text": "Answer: "})
            event_sink({"type": "token", "text": message})
        run = {
            "run_id": "run-session-test", "answer": f"Answer: {message}", "status": "completed",
            "duration_ms": 7, "tool_calls": 0, "steps": 1, "trace": [], "profile": "fast",
            "model": "test-model", "context_attached": bool(context),
            "context_chars": len(context or ""),
        }
        if event_sink:
            event_sink({"type": "run_finished", "run": run})
        return run


class ConversationApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_store = main_module.store
        self.old_agent = main_module.agent
        self.old_data_dir = os.environ.get("INDRA_DATA_DIR")
        os.environ["INDRA_DATA_DIR"] = self.temp.name
        self.store = Store()
        main_module.store = self.store
        main_module.agent = FakeAgent()
        main_module.run_slots.active = 0

    def tearDown(self):
        main_module.store = self.old_store
        main_module.agent = self.old_agent
        if self.old_data_dir is None:
            os.environ.pop("INDRA_DATA_DIR", None)
        else:
            os.environ["INDRA_DATA_DIR"] = self.old_data_dir
        self.temp.cleanup()

    def test_session_round_trip_and_stream_persistence(self):
        with TestClient(main_module.app) as client:
            created = client.post("/api/sessions", json={"title": "New conversation"})
            self.assertEqual(created.status_code, 200, created.text)
            conversation_id = created.json()["conversation_id"]
            response = client.post("/api/chat/stream", json={
                "message": "hello durable world", "history": [], "conversation_id": conversation_id,
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn('"type": "run_finished"', response.text)
            loaded = client.get(f"/api/sessions/{conversation_id}")
            self.assertEqual(loaded.status_code, 200)
            row = loaded.json()
            self.assertEqual(row["title"], "hello durable world")
            self.assertEqual([m["role"] for m in row["messages"]], ["user", "assistant"])
            self.assertEqual(row["messages"][1]["content"], "Answer: hello durable world")
            self.assertEqual(row["messages"][1]["run_id"], "run-session-test")
            renamed = client.patch(f"/api/sessions/{conversation_id}", json={"title": "Research notes"})
            self.assertEqual(renamed.status_code, 200)
            self.assertEqual(renamed.json()["title"], "Research notes")
            self.assertEqual(client.get("/api/sessions").json()[0]["title"], "Research notes")
            deleted = client.delete(f"/api/sessions/{conversation_id}")
            self.assertEqual(deleted.status_code, 200, deleted.text)
            self.assertEqual(client.get(f"/api/sessions/{conversation_id}").status_code, 404)

    def test_context_attachment_reaches_model_once_but_not_saved_user_message(self):
        row = self.store.create_conversation(str(main_module.ensure_workspace()))
        with TestClient(main_module.app) as client:
            response = client.post("/api/chat/stream", json={
                "message": "Summarize this workspace", "conversation_id": row["conversation_id"],
                "context": "--- FILE: README.md ---\nDemo project overview",
            })
            saved = client.get(f"/api/sessions/{row['conversation_id']}").json()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(main_module.agent.last_context, "--- FILE: README.md ---\nDemo project overview")
        self.assertTrue(saved["messages"][1]["content"].startswith("Answer: Summarize this workspace"))
        self.assertNotIn("Demo project overview", saved["messages"][0]["content"])

    def test_context_payload_is_bounded_by_request_schema(self):
        with TestClient(main_module.app) as client:
            response = client.post("/api/chat", json={"message": "hello", "context": "x" * 12001})
        self.assertEqual(response.status_code, 422)

    def test_conversation_workspace_mismatch_is_rejected(self):
        other_workspace = Path(self.temp.name) / "other-workspace"
        other_workspace.mkdir()
        row = self.store.create_conversation(str(other_workspace))
        with TestClient(main_module.app) as client:
            response = client.post("/api/chat/stream", json={
                "message": "do not mix contexts", "history": [], "conversation_id": row["conversation_id"],
            })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.store.get_conversation(row["conversation_id"])["messages"], [])

    def test_export_bundle_is_downloadable_and_redacts_action_content(self):
        self.store.create_conversation(str(main_module.ensure_workspace()), "Export test")
        self.store.add_action({"kind": "write_file", "path": "demo.txt", "content": "secretish project content"})
        with TestClient(main_module.app) as client:
            response = client.get("/api/export")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response.headers.get("content-disposition", ""))
        bundle = response.json()
        self.assertEqual(bundle["product"], "Indra Origo")
        self.assertIn("conversations", bundle)
        self.assertNotIn("content", bundle["actions"][0])
        self.assertIn("Review before sharing", bundle["notice"])

    def test_same_conversation_rejects_parallel_turn(self):
        row = self.store.create_conversation(str(main_module.ensure_workspace()))
        self.assertTrue(main_module.conversation_run_locks.acquire(row["conversation_id"]))
        try:
            with TestClient(main_module.app) as client:
                response = client.post("/api/chat/stream", json={
                    "message": "parallel", "conversation_id": row["conversation_id"],
                })
            self.assertEqual(response.status_code, 409)
        finally:
            main_module.conversation_run_locks.release(row["conversation_id"])


if __name__ == "__main__":
    unittest.main()
