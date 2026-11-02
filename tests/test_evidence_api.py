import tempfile
import unittest
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as main_module
import app.tools as tools
from app.evidence import CapsuleService, ProofLedger


class EvidenceApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        (self.workspace / "metrics.txt").write_text("Accuracy = 92.5% across 17 trials.\n", encoding="utf-8")
        # Use an isolated lightweight persistence double; never touch the user's configured app database in this test.
        self.store = StoreAt(self.root / "store")
        self.capsules = CapsuleService(self.root / "store")
        self.ledger = ProofLedger(self.store)
        self.patchers = [
            patch.object(main_module, "store", self.store),
            patch.object(main_module, "capsule_service", self.capsules),
            patch.object(main_module, "proof_ledger", self.ledger),
            patch.object(tools, "WORKSPACE", self.workspace),
        ]
        for p in self.patchers:
            p.start()
        self.client = TestClient(main_module.app)

    def tearDown(self):
        self.client.close()
        for p in reversed(self.patchers):
            p.stop()
        self.tmp.cleanup()

    def test_capsule_create_verify_download_flow(self):
        created = self.client.post("/api/capsules", json={"workspace_paths": ["metrics.txt"], "include_recent_event_metadata": True})
        self.assertEqual(created.status_code, 200, created.text)
        capsule_id = created.json()["capsule_id"]
        verify = self.client.post(f"/api/capsules/{capsule_id}/verify")
        self.assertEqual(verify.status_code, 200, verify.text)
        self.assertTrue(verify.json()["valid"])
        download = self.client.get(f"/api/capsules/{capsule_id}/download")
        self.assertEqual(download.status_code, 200)
        self.assertIn("application/zip", download.headers["content-type"])
        receipt = self.client.get(f"/api/capsules/{capsule_id}/receipt")
        self.assertEqual(receipt.status_code, 200, receipt.text[:200])
        self.assertIn("text/html", receipt.headers["content-type"])
        self.assertIn("Research artifact integrity receipt", receipt.text)
        self.assertIn("metrics.txt", receipt.text)

    def test_capsule_run_metadata_filters_unrelated_event_content(self):
        self.store.runs = [{"run_id": "run-a", "workspace": str(self.workspace), "status": "done", "prompt": "do not export"}]
        self.store.events = [
            {"event_id": "event-a", "type": "tool", "run_id": "run-a", "content": "private payload"},
            {"event_id": "event-b", "type": "tool", "run_id": "run-b", "content": "other run"},
        ]
        created = self.client.post("/api/capsules", json={"run_id": "run-a", "workspace_paths": []})
        self.assertEqual(created.status_code, 200, created.text)
        path = self.capsules.path_for(created.json()["capsule_id"])
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("capsule_manifest.json"))
        self.assertEqual(manifest["run"]["run_id"], "run-a")
        self.assertNotIn("prompt", manifest["run"])
        self.assertEqual([event["event_id"] for event in manifest["events"]], ["event-a"])
        self.assertNotIn("content", json.dumps(manifest["events"]))

    def test_capsule_refuses_run_from_different_workspace(self):
        other = self.root / "other-workspace"
        other.mkdir()
        self.store.runs = [{"run_id": "other-run", "workspace": str(other), "status": "done"}]
        response = self.client.post("/api/capsules", json={"run_id": "other-run"})
        self.assertEqual(response.status_code, 409, response.text)

    def test_capsule_api_rejects_secret_selection_and_bad_id(self):
        response = self.client.post("/api/capsules", json={"workspace_paths": [".env"]})
        self.assertEqual(response.status_code, 422)
        invalid = self.client.post("/api/capsules/../../oops/verify")
        self.assertNotEqual(invalid.status_code, 200)

    def test_unsupported_claim_cannot_be_manually_cleared_via_api(self):
        claim = self.client.post("/api/proof/claims", json={"statement": "Accuracy was 99%.", "evidence_ids": []})
        self.assertEqual(claim.status_code, 200, claim.text)
        response = self.client.post(f"/api/proof/claims/{claim.json()['claim_id']}/review", json={"reviewed": True})
        self.assertEqual(response.status_code, 409, response.text)

    def test_proof_ledger_evidence_claim_lint_and_review_flow(self):
        evidence = self.client.post("/api/proof/evidence", json={"path": "metrics.txt", "excerpt": "Accuracy = 92.5% across 17 trials."})
        self.assertEqual(evidence.status_code, 200, evidence.text)
        eid = evidence.json()["evidence_id"]
        claim = self.client.post("/api/proof/claims", json={"statement": "Accuracy = 92.5% across 17 trials.", "evidence_ids": [eid]})
        self.assertEqual(claim.status_code, 200, claim.text)
        cid = claim.json()["claim_id"]
        lint = self.client.post("/api/proof/lint", json={"text": "Result: Accuracy = 92.5% across 17 trials.", "claim_ids": [cid]})
        self.assertFalse(lint.json()["export_allowed"])
        review = self.client.post(f"/api/proof/claims/{cid}/review", json={"reviewed": True})
        self.assertEqual(review.status_code, 200)
        lint_after = self.client.post("/api/proof/lint", json={"text": "Result: Accuracy = 92.5% across 17 trials.", "claim_ids": [cid]})
        self.assertTrue(lint_after.json()["export_allowed"])


class StoreAt:
    """Minimal isolated setting/event store for API integration tests."""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings = {}
        self.events = []
        self.runs = []
    def get_setting(self, key, default=None):
        return self.settings.get(key, default)
    def set_setting(self, key, value):
        self.settings[key] = value
    def event(self, kind, **fields):
        row = {"type": kind, **fields}
        self.events.append(row)
        return row
    def list_events(self, limit=200):
        return self.events[-limit:]
    def list_runs(self):
        return self.runs


if __name__ == "__main__":
    unittest.main()
