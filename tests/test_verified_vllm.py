import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from origo_runtime import verified_vllm


class VerifiedVllmTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.model_dir = self.root / "model"
        self.model_dir.mkdir()
        (self.model_dir / "config.json").write_text("{}", encoding="utf-8")
        (self.model_dir / "tokenizer.json").write_text("{}", encoding="utf-8")
        self.weights = self.model_dir / "model.safetensors"
        self.weights.write_bytes(b"test weights")
        self.model_name = "example/test-model"
        self.key = Ed25519PrivateKey.generate()
        self.public_key = self.root / "public.pem"
        self.public_key.write_bytes(
            self.key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
        self.manifest = self.root / "manifest.json"
        self.signature = self.root / "manifest.sig"
        self.approved = verified_vllm.create_manifest(self.model_dir, self.model_name)
        self.sign(self.approved)
        self.flags = [
            str(self.model_dir),
            "--manifest",
            str(self.manifest),
            "--signature",
            str(self.signature),
            "--trusted-key",
            str(self.public_key),
        ]

    def sign(self, payload, *, key=None):
        self.manifest.write_bytes(payload)
        self.signature.write_bytes((key or self.key).sign(payload))

    def verify(self):
        return verified_vllm.verify_model(
            self.model_dir, self.manifest, self.signature, self.public_key
        )

    def test_verify_cli_reports_digest_under_pinned_release_key(self):
        result = subprocess.run(
            [sys.executable, "-m", "origo_runtime.verified_vllm", "verify", *self.flags],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(
            json.loads(result.stdout),
            {
                "model": self.model_name,
                "manifest_sha256": hashlib.sha256(self.approved).hexdigest(),
            },
        )

    def test_fails_closed_when_signature_is_from_another_key(self):
        self.sign(self.approved, key=Ed25519PrivateKey.generate())
        with self.assertRaisesRegex(ValueError, "signature did not verify"):
            self.verify()

    def test_fails_closed_for_altered_missing_or_extra_model_files(self):
        with self.subTest("altered tokenizer"):
            tokenizer = self.model_dir / "tokenizer.json"
            tokenizer.write_text('{"different": true}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "do not match"):
                self.verify()
            tokenizer.write_text("{}", encoding="utf-8")
        with self.subTest("unsigned weight shard"):
            extra = self.model_dir / "extra.safetensors"
            extra.write_bytes(b"unsigned")
            with self.assertRaisesRegex(ValueError, "do not match"):
                self.verify()
            extra.unlink()
        with self.subTest("missing weights"):
            self.weights.unlink()
            with self.assertRaisesRegex(ValueError, "safetensors weights"):
                self.verify()

    def test_rejects_signed_inventory_paths_outside_the_model(self):
        manifest = json.loads(self.approved)
        manifest["files"]["../public.pem"] = hashlib.sha256(
            self.public_key.read_bytes()
        ).hexdigest()
        self.sign(verified_vllm._manifest_bytes(manifest))
        with self.assertRaisesRegex(ValueError, "do not match"):
            self.verify()

    def test_rejects_symlinks_in_model_tree(self):
        try:
            (self.model_dir / "external.json").symlink_to(self.public_key)
        except OSError as exc:
            self.skipTest(f"Host cannot create a symlink: {exc}")
        with self.assertRaisesRegex(ValueError, "link or reparse point"):
            self.verify()

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux model serving")
    def test_cannot_launch_from_writable_mount(self):
        with (
            patch.dict(os.environ, {"VLLM_API_KEY": "test-only"}),
            patch.object(os, "execve") as run,
        ):
            self.assertEqual(verified_vllm.main(["serve", *self.flags]), 1)
            run.assert_not_called()

    def test_launch_strips_unapproved_loader_overrides_and_binds_loopback(self):
        settings = {
            "VLLM_API_KEY": "test-only",
            "VLLM_MODEL_REDIRECT_PATH": "unapproved",
            "HF_ENDPOINT": "unapproved",
        }
        with (
            patch.object(sys, "platform", "linux"),
            patch.object(verified_vllm, "_require_read_only"),
            patch.object(os, "execve") as run,
            patch.dict(os.environ, settings),
        ):
            self.assertEqual(verified_vllm.main(["serve", *self.flags]), 0)
        executable, command, environment = run.call_args.args
        self.assertEqual(executable, sys.executable)
        self.assertEqual(command[command.index("--host") + 1], "127.0.0.1")
        self.assertEqual(command[command.index("--tokenizer") + 1], str(self.model_dir))
        self.assertEqual(command[command.index("--load-format") + 1], "safetensors")
        self.assertEqual(environment["HF_HUB_OFFLINE"], "1")
        self.assertEqual(environment["VLLM_API_KEY"], "test-only")
        self.assertEqual(environment["VLLM_PLUGINS"], "")
        self.assertNotIn("VLLM_MODEL_REDIRECT_PATH", environment)
        self.assertNotIn("HF_ENDPOINT", environment)
