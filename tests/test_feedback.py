"""Regression tests for the optional, content-free human outcome-review loop."""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import app.main as main_module
from app.store import Store


class OutcomeFeedbackApiTests(unittest.TestCase):
    def setUp(self):
        self.previous_store = main_module.store
        self.previous_data_dir = os.environ.get("INDRA_DATA_DIR")
        self.temp = tempfile.TemporaryDirectory()
        os.environ["INDRA_DATA_DIR"] = self.temp.name
        main_module.store = Store()
        self.conversation = main_module.store.create_conversation("/tmp/test-workspace", "Feedback test")
        self.run_id = "a" * 32
        main_module.store.append_conversation_message(self.conversation["conversation_id"], "user", "private prompt text")
        main_module.store.append_conversation_message(
            self.conversation["conversation_id"], "assistant", "private answer text",
            run_id=self.run_id, status="completed",
        )
        self.client = TestClient(main_module.app)

    def tearDown(self):
        self.client.close()
        main_module.store = self.previous_store
        if self.previous_data_dir is None:
            os.environ.pop("INDRA_DATA_DIR", None)
        else:
            os.environ["INDRA_DATA_DIR"] = self.previous_data_dir
        self.temp.cleanup()

    def test_rating_is_content_free_editable_and_not_sent_to_the_model(self):
        with patch.object(main_module.provider, "chat", new_callable=AsyncMock) as model_call:
            useful = self.client.post("/api/feedback", json={
                "run_id": self.run_id,
                "conversation_id": self.conversation["conversation_id"],
                "rating": "useful",
            })
            incorrect = self.client.post("/api/feedback", json={
                "run_id": self.run_id,
                "conversation_id": self.conversation["conversation_id"],
                "rating": "incorrect",
            })
        self.assertEqual(useful.status_code, 200, useful.text)
        self.assertEqual(incorrect.status_code, 200, incorrect.text)
        self.assertFalse(model_call.called)
        summary = self.client.get("/api/feedback").json()
        conversation_summary = self.client.get(
            f"/api/feedback?conversation_id={self.conversation['conversation_id']}"
        ).json()
        self.assertEqual(summary["total"], 1, summary)
        self.assertEqual(summary["counts"]["incorrect"], 1)
        self.assertEqual(summary["counts"]["useful"], 0)
        self.assertEqual(summary["by_run"], {})  # Do not disclose run-level labels globally.
        self.assertEqual(conversation_summary["by_run"][self.run_id], "incorrect")
        self.assertTrue(summary["local_only"])
        self.assertFalse(summary["sent_to_model"])
        self.assertFalse(summary["used_for_training"])
        self.assertFalse(summary["automatic_adaptation"])
        self.assertNotIn("private prompt text", str(summary))
        self.assertNotIn("private answer text", str(summary))

    def test_rating_requires_the_run_to_belong_to_the_named_conversation(self):
        other = main_module.store.create_conversation("/tmp/test-workspace", "Other conversation")
        response = self.client.post("/api/feedback", json={
            "run_id": self.run_id,
            "conversation_id": other["conversation_id"],
            "rating": "useful",
        })
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(self.client.get("/api/feedback").json()["total"], 0)

    def test_invalid_rating_and_malformed_ids_are_rejected(self):
        bad_rating = self.client.post("/api/feedback", json={
            "run_id": self.run_id,
            "conversation_id": self.conversation["conversation_id"],
            "rating": "five_stars",
        })
        bad_id = self.client.post("/api/feedback", json={
            "run_id": "bad-id",
            "conversation_id": self.conversation["conversation_id"],
            "rating": "useful",
        })
        self.assertEqual(bad_rating.status_code, 422)
        self.assertEqual(bad_id.status_code, 422)

    def test_user_can_remove_rating_without_deleting_run_or_conversation(self):
        payload = {
            "run_id": self.run_id,
            "conversation_id": self.conversation["conversation_id"],
            "rating": "risky",
        }
        self.assertEqual(self.client.post("/api/feedback", json=payload).status_code, 200)
        removed = self.client.delete(
            f"/api/feedback/{self.run_id}?conversation_id={self.conversation['conversation_id']}"
        )
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertTrue(removed.json()["deleted"])
        self.assertEqual(self.client.get("/api/feedback").json()["total"], 0)
        conversation = self.client.get(f"/api/sessions/{self.conversation['conversation_id']}")
        self.assertEqual(conversation.status_code, 200)
        self.assertEqual(len(conversation.json()["messages"]), 2)

    def test_clear_all_only_deletes_ratings_and_is_idempotent(self):
        self.client.post("/api/feedback", json={
            "run_id": self.run_id,
            "conversation_id": self.conversation["conversation_id"],
            "rating": "incomplete",
        })
        first = self.client.delete("/api/feedback")
        second = self.client.delete("/api/feedback")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["deleted"], 1)
        self.assertEqual(second.json()["deleted"], 0)
        self.assertEqual(self.client.get("/api/feedback").json()["total"], 0)
        self.assertEqual(len(self.client.get(f"/api/sessions/{self.conversation['conversation_id']}").json()["messages"]), 2)

    def test_feedback_is_removed_when_user_deletes_its_conversation(self):
        self.client.post("/api/feedback", json={
            "run_id": self.run_id,
            "conversation_id": self.conversation["conversation_id"],
            "rating": "useful",
        })
        deleted = self.client.delete(f"/api/sessions/{self.conversation['conversation_id']}")
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(self.client.get("/api/feedback").json()["total"], 0)


if __name__ == "__main__":
    unittest.main()
