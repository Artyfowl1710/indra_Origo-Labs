"""Run the Windows launcher against isolated files and a desktop launch receiver."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "Windows launcher")
class OptionalLocalLauncherTests(unittest.TestCase):
    def launch(self, unverified=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy2(ROOT / "start_origo_auto.ps1", root / "start_origo_auto.ps1")
            runtime = root / "local/Programs/Ollama/lib/ollama"
            runtime.mkdir(parents=True)
            if unverified:
                (runtime / "llama-server.exe").write_bytes(b"untrusted fixture, never executable")
            (root / "start_origo_product.ps1").write_text(
                "@{routing=$env:ORIGO_AUTO_ROUTING;issue=$env:ORIGO_LOCAL_STARTUP_ISSUE;"
                "home=$env:ORIGO_HOME} | ConvertTo-Json -Compress", encoding="utf-8")
            # A malformed old ownership record must not be consulted when no engine
            # will start; no process lookup or termination is needed for API use.
            (root / "data").mkdir()
            (root / "data/cpp-runtime.json").write_text("not valid json", encoding="utf-8")
            home = root / "data/indra-auto-home"
            home.mkdir()
            config = home / "config.yaml"
            original = b"model:\n  provider: baseten\n  default: meta-models/muse-spark-open-1026\n"
            config.write_bytes(original)
            env = {key:value for key,value in os.environ.items()
                   if key.upper() in {"PATH","SYSTEMROOT","WINDIR","TEMP","TMP","USERPROFILE","PSMODULEPATH"}}
            env["LOCALAPPDATA"] = str(root / "local")
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(root / "start_origo_auto.ps1"), "-ModelDirectory", str(root / "absent-models")],
                env=env, capture_output=True, text=True, timeout=25)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(config.read_bytes(), original)
            payload = json.loads(result.stdout.strip())
            self.assertEqual(payload["routing"], "0")
            self.assertEqual(Path(payload["home"]), home)
            return payload

    def test_missing_runtime_still_launches_same_profile(self):
        self.assertEqual(self.launch()["issue"], "runtime-missing")

    def test_unverified_runtime_is_not_started_but_desktop_still_launches(self):
        self.assertEqual(self.launch(unverified=True)["issue"], "runtime-unverified")
