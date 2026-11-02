import os
import tempfile
import unittest
from fastapi.testclient import TestClient

import app.main as main_module
from app.store import Store


class BombAgent:
    async def run(self, *args, **kwargs):
        raise AssertionError("Scout must never invoke the model agent")


class ScoutApiTests(unittest.TestCase):
    def setUp(self):
        self.old_agent = main_module.agent
        self.old_store = main_module.store
        self.old_data_dir = os.environ.get("INDRA_DATA_DIR")
        self.temp = tempfile.TemporaryDirectory()
        os.environ["INDRA_DATA_DIR"] = self.temp.name
        main_module.store = Store()
        main_module.agent = BombAgent()

    def tearDown(self):
        main_module.agent = self.old_agent
        main_module.store = self.old_store
        if self.old_data_dir is None:
            os.environ.pop("INDRA_DATA_DIR", None)
        else:
            os.environ["INDRA_DATA_DIR"] = self.old_data_dir
        self.temp.cleanup()

    def test_scout_status_is_explicit_about_read_only_scope(self):
        with TestClient(main_module.app) as client:
            response = client.get("/api/scout/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["model_inference"])
        self.assertFalse(data["outbound_network"])
        self.assertFalse(data["writes"])
        self.assertFalse(data["approvals_granted"])

    def test_scout_run_exercises_safe_routes_without_model_calls(self):
        with TestClient(main_module.app) as client:
            response = client.post("/api/scout/run", json={})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["agent"], "Origo Scout")
        self.assertEqual(data["status"], "pass", data)
        self.assertEqual(data["summary"]["failed"], 0)
        self.assertGreaterEqual(data["summary"]["total"], 10)
        self.assertTrue(all(row["status"] == "pass" for row in data["checks"]))
        self.assertFalse(data["safety_contract"]["model_inference"])
        self.assertFalse(data["safety_contract"]["writes"])
        self.assertFalse(data["safety_contract"]["outbound_network"])

    def test_scout_reports_bounded_evidence_not_workspace_or_conversation_content(self):
        with TestClient(main_module.app) as client:
            response = client.post("/api/scout/run", json={})
        body = response.text
        self.assertNotIn("INDRA_DATA_DIR", body)
        self.assertNotIn("api_key", body.lower())
        self.assertNotIn("conversation title", body.lower())
        for check in response.json()["checks"]:
            self.assertLessEqual(len(check.get("evidence", "")), 240)


if __name__ == "__main__":
    unittest.main()
