import base64
import concurrent.futures
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from urllib.parse import quote

from origo_runtime.canaries import CanaryRegistry, CanaryScanError
from origo_runtime.audit import AuditLog


class CanaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = CanaryRegistry(self.root)
        self.row = self.registry.create("profile-a")
        self.token = self.row["token"]

    def test_hash_only_storage_restart_and_cross_profile_detection(self):
        self.assertNotIn(self.token.encode(), self.registry.path.read_bytes())
        with closing(sqlite3.connect(self.registry.path)) as db:
            self.assertEqual(db.execute("SELECT digest FROM canaries").fetchone()[0], hashlib.sha256(self.token.encode()).hexdigest())
        registry = CanaryRegistry(self.root)
        self.assertEqual(registry.matches({"another-profile-request": self.token}), [self.row["id"]])
        self.assertEqual(registry.list("profile-b"), [])
        self.assertNotIn("token", registry.list("profile-a")[0])

    def test_nested_values_keys_and_common_encodings(self):
        encoded = base64.b64encode(self.token.encode()).decode()
        variants = [self.token, self.token[:20]+"\u200b"+self.token[20:], " ".join(self.token),
                    quote(self.token, safe="").replace("_", "%5F"), encoded,
                    base64.b64encode(encoded.encode()).decode(),
                    "".join("\\u%04x" % ord(c) for c in self.token),
                    "".join(chr(ord(c)+0xfee0) if "!" <= c <= "~" else c for c in self.token)]
        for value in variants:
            with self.subTest(value=variants.index(value)):
                self.assertEqual(self.registry.matches({"messages": [{"content": value}]}), [self.row["id"]])
        self.assertEqual(self.registry.matches({self.token: "key"}), [self.row["id"]])

    def test_unregistered_and_normal_payloads_pass_unchanged(self):
        payload = {"messages": [{"content": "ordinary private notes"}], "tools": []}
        original = json.dumps(payload)
        self.assertEqual(self.registry.matches(payload), [])
        self.assertEqual(self.registry.matches("INDRA_CANARY_"+"x"*43), [])
        self.assertEqual(json.dumps(payload), original)

    def test_signed_incident_contains_no_raw_content(self):
        audit = AuditLog(self.root / "profile-a")
        blocked = self.registry.veto({"command": self.token}, audit, channel="tool", session="chat", turn="turn")
        self.assertEqual(blocked["action"], "block")
        serialized = json.dumps(audit.recent()) + json.dumps(blocked)
        self.assertNotIn(self.token, serialized)
        self.assertIn(self.row["id"], serialized)
        self.assertTrue(audit.verify()["valid"])

    def test_corrupt_registry_and_payload_limits_do_not_allow(self):
        cyclic = []; cyclic.append(cyclic)
        with self.assertRaises(CanaryScanError): self.registry.matches(cyclic)
        with self.assertRaises(CanaryScanError): self.registry.matches("x"*(32*1024*1024+1))
        self.registry.path.write_bytes(b"broken registry")
        with self.assertRaises(sqlite3.DatabaseError): self.registry.matches("hello")

    def test_concurrent_registration_and_detection(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(lambda n: self.registry.create("owner", "Canary %s" % n), range(8)))
        self.assertEqual(len(self.registry.matches([row["token"] for row in rows])), 8)

    def test_marker_file_excluded_from_knowledge(self):
        from app.rag import _is_blocked_filename
        self.assertTrue(_is_blocked_filename(".indra-canary.txt"))

    def test_invalid_labels_rejected(self):
        for label in ["", "a"*65, "name\nsecret", "../vault"]:
            with self.assertRaises(ValueError): self.registry.create("owner", label)

    def test_setup_writes_only_explicit_file_and_refuses_overwrite(self):
        import contextlib, io
        from unittest.mock import patch
        from scripts import manage_canaries as cli
        home = self.root / "profile"; home.mkdir()
        (home / "config.yaml").write_text("security:\n  untrusted_content_guard: true\n")
        vault = self.root / "vault"; vault.mkdir()
        argv = ["manage_canaries.py", "create", "--profile-home", str(home), "--vault-folder", str(vault)]
        output = io.StringIO()
        with patch.object(cli, "ROOT", self.root), patch("sys.argv", argv), contextlib.redirect_stdout(output):
            cli.main()
            marker = (vault / ".indra-canary.txt").read_text().strip()
            self.assertNotIn(marker, output.getvalue())
            self.assertEqual(len(CanaryRegistry(self.root / "data").matches(marker)), 1)
            with self.assertRaises(FileExistsError): cli.main()
            self.assertEqual((vault / ".indra-canary.txt").read_text().strip(), marker)

    def test_setup_requires_active_guard_before_touching_vault(self):
        import contextlib, io
        from unittest.mock import patch
        from scripts import manage_canaries as cli
        home = self.root / "profile"; home.mkdir()
        (home / "config.yaml").write_text("security: {}")
        vault = self.root / "vault"; vault.mkdir()
        argv = ["manage_canaries.py", "create", "--profile-home", str(home), "--vault-folder", str(vault)]
        with patch.object(cli, "ROOT", self.root), patch("sys.argv", argv), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): cli.main()
        self.assertEqual(list(vault.iterdir()), [])
