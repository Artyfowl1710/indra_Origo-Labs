import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class ProfileBootstrapTests(unittest.TestCase):
    def run_bootstrap(self, cfg, existing=True, selected_home=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "scripts").mkdir()
        script = root / "scripts/configure_cpp_profile.py"
        shutil.copy2(ROOT / "scripts/configure_cpp_profile.py", script)
        default_home = root / "data/indra-auto-home"
        home = root / ("data/custom-selected-home" if selected_home else "data/indra-auto-home")
        home.mkdir(parents=True)
        for name in ("skills", "skins", "dashboard-themes"):
            (home / name).mkdir()
        source = home / "config.yaml" if existing else root / "data/indra-local-home/config.yaml"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        env = {key: value for key, value in os.environ.items() if key.upper() in {
            "SYSTEMROOT", "WINDIR", "PATH", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP"}}
        env.update({"PYTHONPATH": str(ROOT), "ORIGO_CPP_PROFILE": "indra-auto-home", "ORIGO_CPP_ALIAS": "origo-auto",
                    "ORIGO_CPP_ORIGIN": "http://127.0.0.1:49999", "ORIGO_LOCAL_INFERENCE_KEY": "fixture-token-" + "a" * 32})
        if selected_home:
            env["ORIGO_HOME"] = str(home)
            default_home.mkdir(parents=True)
            (default_home / "config.yaml").write_text("original: untouched\n", encoding="utf-8")
        subprocess.run([sys.executable, str(script)], env=env, capture_output=True, check=True, timeout=30)
        if selected_home:
            self.assertEqual((default_home / "config.yaml").read_text(encoding="utf-8"), "original: untouched\n")
            self.assertFalse((default_home / ".env").exists())
        return yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))

    def test_selected_profile_is_the_only_home_updated(self):
        cfg = {"model": {"provider": "baseten", "default": "meta-models/muse-spark-open-1026"}}
        after = self.run_bootstrap(cfg, selected_home=True)
        self.assertEqual(after["model"], cfg["model"])
        self.assertIn("origo-local", after["providers"])

    def test_cloud_selection_and_explicit_auxiliary_pin_survive_restart(self):
        cfg = {"model": {"provider": "openrouter", "default": "test/reader:free"},
               "auxiliary": {"vision": {"provider": "openrouter", "model": "test/vision:free"}}}
        after = self.run_bootstrap(cfg)
        self.assertEqual(after["model"], cfg["model"])
        self.assertEqual(after["auxiliary"], cfg["auxiliary"])
        self.assertIn("origo-local", after["providers"])

    def test_desktop_enables_content_guard_and_preserves_explicit_opt_out(self):
        after=self.run_bootstrap({"model":{"provider":"openrouter","default":"test/text"}})
        self.assertTrue(after["security"]["untrusted_content_guard"])
        after=self.run_bootstrap({"model":{"provider":"openrouter","default":"test/text"},"security":{"untrusted_content_guard":False}})
        self.assertFalse(after["security"]["untrusted_content_guard"])

    def test_local_vision_pin_receives_rotated_endpoint_while_main_stays_cloud(self):
        after = self.run_bootstrap({"model": {"provider": "openrouter", "default": "test/text"},
            "auxiliary": {"vision": {"provider": "custom", "model": "origo-auto", "base_url": "http://127.0.0.1:1/v1"}}})
        self.assertEqual(after["model"]["provider"], "openrouter")
        self.assertEqual(after["auxiliary"]["vision"]["base_url"], "http://127.0.0.1:49999/v1")

    def test_first_launch_still_creates_local_routing_default(self):
        after = self.run_bootstrap({"model": {}}, existing=False)
        self.assertEqual(after["model"]["provider"], "custom:origo-local")
        self.assertTrue(after["model"]["supports_vision"])
        self.assertEqual(after["agent"]["image_input_mode"], "auto")
