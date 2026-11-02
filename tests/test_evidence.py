import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
import zipfile
from pathlib import Path
from unittest.mock import patch

from app.evidence import CapsuleService, ProofLedger
from app.store import Store


class CapsuleServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        (self.workspace / "results.txt").write_text("accuracy=92.5%\nseed=17\n", encoding="utf-8")
        (self.workspace / "notes.md").write_text("A deterministic local result.", encoding="utf-8")
        (self.workspace / ".env").write_text("API_KEY=must-not-export", encoding="utf-8")
        self.service = CapsuleService(self.root / "data")

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_sign_verify_selected_file_and_trusted_signer(self):
        created = self.service.create(self.workspace, run={"run_id": "r1", "prompt": "private prompt", "status": "done"},
                                      events=[{"type": "run", "content": "private"}], paths=["results.txt"])
        path = self.service.path_for(created["capsule_id"])
        report = self.service.verify(path)
        self.assertTrue(report["valid"], report)
        self.assertTrue(report["signature_valid"])
        self.assertTrue(report["files_valid"])
        self.assertTrue(report["signer_trusted_by_this_install"])
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            self.assertIn("workspace/results.txt", names)
            self.assertNotIn("workspace/.env", names)
            manifest = json.loads(archive.read("capsule_manifest.json"))
            self.assertNotIn("prompt", manifest["run"])
            self.assertNotIn("content", json.dumps(manifest["events"]))

    def test_rejects_path_traversal_symlinks_and_secret_files(self):
        for bad in ("../outside.txt", ".env", "data/indra.sqlite3"):
            with self.subTest(path=bad), self.assertRaises(ValueError):
                self.service.create(self.workspace, run=None, events=[], paths=[bad])
        outside = self.root / "outside.txt"
        outside.write_text("no", encoding="utf-8")
        try:
            (self.workspace / "linked.txt").symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available on this platform")
        with self.assertRaises(ValueError):
            self.service.create(self.workspace, run=None, events=[], paths=["linked.txt"])

    def test_tamper_breaks_manifest_signature(self):
        created = self.service.create(self.workspace, run=None, events=[], paths=["results.txt"])
        path = self.service.path_for(created["capsule_id"])
        altered = self.root / "altered.zip"
        with zipfile.ZipFile(path) as src, zipfile.ZipFile(altered, "w", zipfile.ZIP_DEFLATED) as dst:
            for name in src.namelist():
                data = src.read(name)
                if name == "workspace/results.txt":
                    data = b"accuracy=99%"
                dst.writestr(name, data)
        report = self.service.verify(altered)
        self.assertFalse(report["valid"])
        self.assertIn("hash_mismatch:workspace/results.txt", report["problems"])

    def test_secret_scanner_blocks_likely_inline_credentials(self):
        (self.workspace / "config.txt").write_text("API_KEY=sk-" + "A" * 32, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Likely secret material detected"):
            self.service.create(self.workspace, run=None, events=[], paths=["config.txt"])

    def test_verifier_rejects_archive_with_too_many_entries(self):
        overloaded = self.root / "many.zip"
        with zipfile.ZipFile(overloaded, "w", zipfile.ZIP_DEFLATED) as archive:
            for index in range(601):
                archive.writestr(f"f{index}.txt", "x")
        report = self.service.verify(overloaded)
        self.assertFalse(report["valid"])
        self.assertIn("unreadable_or_incomplete_archive:ValueError", report["problems"])

    def test_verifier_rejects_non_zip_and_invalid_identifier(self):
        bad = self.root / "bad.zip"
        bad.write_text("not zip", encoding="utf-8")
        report = self.service.verify(bad)
        self.assertFalse(report["valid"])
        with self.assertRaises(ValueError):
            self.service.path_for("../../oops")


class ProofLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        (self.workspace / "metrics.txt").write_text("Accuracy = 92.5% on seed 17.\nThe run is reproducible only under the pinned environment.", encoding="utf-8")
        self.store = StoreForTest(self.root / "store")
        self.ledger = ProofLedger(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_evidence_requires_exact_excerpt_and_claim_numeric_match(self):
        evidence = self.ledger.add_evidence(self.workspace, "metrics.txt", "Accuracy = 92.5% on seed 17.")
        claim = self.ledger.add_claim("Accuracy = 92.5% on seed 17.", [evidence["evidence_id"]])
        self.assertEqual(claim["status"], "numeric_match_semantics_unverified")
        lint = self.ledger.lint("Reported: Accuracy = 92.5% on seed 17.", [claim["claim_id"]])
        self.assertFalse(lint["export_allowed"])
        with self.assertRaises(ValueError):
            self.ledger.add_evidence(self.workspace, "metrics.txt", "this text is not present")

    def test_numeric_mismatch_and_missing_evidence_are_flagged(self):
        evidence = self.ledger.add_evidence(self.workspace, "metrics.txt", "Accuracy = 92.5% on seed 17.")
        wrong = self.ledger.add_claim("Accuracy = 99% on seed 17.", [evidence["evidence_id"]])
        unsupported = self.ledger.add_claim("We achieved 99% accuracy.", [])
        self.assertEqual(wrong["status"], "numeric_mismatch")
        self.assertEqual(unsupported["status"], "unsupported")
        report = self.ledger.lint(wrong["statement"] + " " + unsupported["statement"], [wrong["claim_id"], unsupported["claim_id"]])
        self.assertEqual(report["summary"]["flagged"], 2)
        self.assertFalse(report["export_allowed"])

    def test_source_change_marks_evidence_stale_and_review_cannot_clear_it(self):
        evidence = self.ledger.add_evidence(self.workspace, "metrics.txt", "Accuracy = 92.5% on seed 17.")
        claim = self.ledger.add_claim("Accuracy = 92.5% on seed 17.", [evidence["evidence_id"]], workspace=self.workspace)
        (self.workspace / "metrics.txt").write_text("Accuracy = 99.9% on seed 18.\n", encoding="utf-8")
        report = self.ledger.lint(claim["statement"], [claim["claim_id"]], workspace=self.workspace)
        self.assertEqual(report["findings"][0]["status"], "stale_evidence")
        with self.assertRaisesRegex(ValueError, "stale evidence"):
            self.ledger.review_claim(claim["claim_id"], True, workspace=self.workspace)

    def test_unsupported_claim_cannot_be_cleared_by_manual_review(self):
        claim = self.ledger.add_claim("We achieved 99% accuracy.", [])
        with self.assertRaisesRegex(ValueError, "missing, mismatched, or stale evidence"):
            self.ledger.review_claim(claim["claim_id"], True, workspace=self.workspace)

    def test_concurrent_claim_registrations_do_not_lose_updates(self):
        def add(index):
            return self.ledger.add_claim(f"Hypothesis note {index} needs review.", [])
        with ThreadPoolExecutor(max_workers=8) as pool:
            claims = list(pool.map(add, range(40)))
        stored = self.ledger.get()["claims"]
        self.assertEqual(len(claims), 40)
        self.assertEqual(len(stored), 40)
        self.assertEqual(len({claim["claim_id"] for claim in stored}), 40)

    def test_non_numeric_claim_still_requires_human_review(self):
        evidence = self.ledger.add_evidence(self.workspace, "metrics.txt", "The run is reproducible only under the pinned environment.")
        claim = self.ledger.add_claim("The run is reproducible only under the pinned environment.", [evidence["evidence_id"]])
        self.assertEqual(claim["status"], "human_review_required")


class StoreForTest:
    """Small persistent setting store double for focused Proof Ledger unit tests."""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.values = {}
    def get_setting(self, key, default=None):
        return self.values.get(key, default)
    def set_setting(self, key, value):
        self.values[key] = value


if __name__ == "__main__":
    unittest.main()
