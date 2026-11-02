import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dotenv import dotenv_values
from origo_runtime.phone_config import (
    normalize_endpoint, save_settings, read_settings, disable_settings, apply_settings,
    SETTINGS_NAME, SECRET_ENV, HASH_ENV,
)


class PhoneConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.payload = {"endpoint": "https://origo.private-tailnet.ts.net", "username": "origo",
                        "password": "local-fixture-password-123", "port": 8766}

    def test_endpoint_restrictions(self):
        for value in ["http://origo.private-tailnet.ts.net", "https://evil.example", "https://pc.ts.net.evil.example",
                      "https://user@pc.ts.net", "https://pc.ts.net:8443", "https://pc.ts.net/path",
                      "https://pc.ts.net?", "https://pc.ts.net#", "https://.ts.net", "https://bad_label.ts.net",
                      "https://pc.ts.net\r\nHost: evil", "file:///private", "https://pc.ts.net/%2e%2e"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_endpoint(value)
        self.assertEqual(normalize_endpoint("HTTPS://PC.PRIVATE.ts.net:443/"), "https://pc.private.ts.net")

    def test_password_is_hashed_and_secrets_never_returned_to_native_ui(self):
        row = save_settings(self.home, self.payload)
        self.assertNotIn("password", row)
        self.assertEqual(read_settings(self.home), row)
        self.assertNotIn(self.payload["password"], (self.home / ".env").read_text())
        env = dotenv_values(self.home / ".env")
        self.assertTrue(env[HASH_ENV].startswith("scrypt$"))
        self.assertGreaterEqual(len(env[SECRET_ENV]), 32)
        from plugins.dashboard_auth.basic import _verify_password
        self.assertTrue(_verify_password(self.payload["password"], env[HASH_ENV]))
        self.assertFalse(_verify_password("wrong-fixture-password", env[HASH_ENV]))

    def test_rotation_revokes_old_signing_secret_and_preserves_model_credentials(self):
        (self.home / ".env").write_text("ORIGO_LOCAL_INFERENCE_KEY=model-fixture-key\n")
        save_settings(self.home, self.payload)
        first = dotenv_values(self.home / ".env")[SECRET_ENV]
        save_settings(self.home, self.payload)
        env = dotenv_values(self.home / ".env")
        self.assertNotEqual(first, env[SECRET_ENV])
        self.assertEqual(env["ORIGO_LOCAL_INFERENCE_KEY"], "model-fixture-key")

    def test_disable_keeps_authentication_and_rotates_sessions(self):
        save_settings(self.home, self.payload)
        before = dotenv_values(self.home / ".env")[SECRET_ENV]
        disable_settings(self.home)
        self.assertFalse(read_settings(self.home)["enabled"])
        self.assertNotEqual(before, dotenv_values(self.home / ".env")[SECRET_ENV])
        config = apply_settings(self.home, {})
        self.assertEqual(config["dashboard"]["public_url"], self.payload["endpoint"])
        self.assertEqual(config["dashboard"]["basic_auth"]["username"], "origo")

    def test_invalid_setup_does_not_write_settings(self):
        for fields in [{"password": "short"}, {"port": True}, {"port": 1}, {"username": "../admin"},
                       {"extra": "unknown"}]:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                save_settings(self.home, {**self.payload, **fields})
            self.assertFalse((self.home / SETTINGS_NAME).exists())

    def test_missing_credentials_fail_closed(self):
        save_settings(self.home, self.payload)
        (self.home / ".env").write_text("")
        with self.assertRaises(ValueError):
            apply_settings(self.home, {})

    def test_malformed_and_oversized_settings_fail_closed(self):
        path = self.home / SETTINGS_NAME
        for content in ["{", "[]", "x" * 4097]:
            path.write_text(content)
            with self.assertRaises(ValueError):
                read_settings(self.home)

    def test_permission_failure_does_not_publish_settings(self):
        with patch("origo_runtime.phone_config.set_key", side_effect=PermissionError("fixture")):
            with self.assertRaises(PermissionError):
                save_settings(self.home, self.payload)
        self.assertFalse((self.home / SETTINGS_NAME).exists())

    def test_local_profile_without_phone_setup_is_unchanged(self):
        config = {"model": {"default": "origo-auto"}}
        before = copy.deepcopy(config)
        self.assertEqual(apply_settings(self.home, config), before)


if __name__ == "__main__":
    unittest.main()
