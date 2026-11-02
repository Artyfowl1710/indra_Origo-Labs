import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import psutil

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "scripts/job_lifetime_fixture.py"


@unittest.skipUnless(os.name == "nt", "Real Windows job-object process containment")
class ProcessLifetimeTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / "data/test-results"
        parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="origo-job-", dir=parent)
        self.directory = Path(self.temporary.name)
        self.launchers = []
        self.addCleanup(self.cleanup)

    def spawn(self, role):
        with (self.directory / (role + "-error.log")).open("ab") as log:
            child = subprocess.Popen([sys.executable, "-u", str(FIXTURE), role, str(self.directory)],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
        self.launchers.append(child)
        return child

    def receipt(self, role):
        path = self.directory / (role + ".json")
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
            time.sleep(.05)
        diagnostics = "\n".join(path.read_text(errors="replace")[-2000:] for path in self.directory.glob("*-error.log"))
        self.fail("Disposable fixture did not become ready: " + role + "\n" + diagnostics)

    def alive(self, receipt):
        try:
            process = psutil.Process(receipt["pid"])
            return process.is_running() and abs(process.create_time() - receipt["created"]) < .01
        except psutil.NoSuchProcess:
            return False

    def assert_dead(self, receipt):
        deadline = time.monotonic() + 8
        while self.alive(receipt) and time.monotonic() < deadline:
            time.sleep(.05)
        self.assertFalse(self.alive(receipt), "An owned disposable worker survived its owner")

    def cleanup(self):
        # Receipts identify only this fixture's own processes, including a
        # possible escaped-worker failure. Never scan/kill by executable name.
        for path in self.directory.glob("*.json"):
            receipt = json.loads(path.read_text(encoding="utf-8"))
            if "created" in receipt and self.alive(receipt):
                try:
                    process = psutil.Process(receipt["pid"])
                    process.kill()
                    process.wait(timeout=5)
                except psutil.NoSuchProcess:
                    pass
        for child in self.launchers:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
        deadline = time.monotonic() + 5
        while True:
            try:
                self.temporary.cleanup()
                break
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.1)

    def test_abrupt_owner_death_reaps_descendants_and_spares_unrelated_process(self):
        self.spawn("control")
        control = self.receipt("control")
        self.spawn("owner")
        owner, child, leaf = (self.receipt(role) for role in ("owner", "child", "leaf"))
        job = self.receipt("job")
        self.assertIn(child["pid"], job["members"], str(job))
        self.assertIn(leaf["pid"], job["members"], str(job))
        self.assertFalse(job["handle_inheritable"], str(job))
        process = psutil.Process(owner["pid"])
        self.assertTrue(self.alive(owner))
        process.kill()
        self.assert_dead(child)
        self.assert_dead(leaf)
        self.assertTrue(self.alive(control), "An unrelated fixture process was terminated")

    def test_normal_owner_exit_reaps_descendants_and_disallows_breakaway(self):
        launcher = self.spawn("owner")
        owner, child, leaf = (self.receipt(role) for role in ("owner", "child", "leaf"))
        self.receipt("job")
        self.assertTrue(self.receipt("breakaway")["blocked"], "A worker escaped its strict service job")
        (self.directory / "stop-owner").touch()
        launcher.wait(timeout=10)
        self.assert_dead(owner)
        self.assert_dead(child)
        self.assert_dead(leaf)

    def test_strict_request_refuses_an_already_weaker_job(self):
        launcher = self.spawn("weaker")
        result = self.receipt("weaker-result")
        launcher.wait(timeout=10)
        self.assertTrue(result["attached"])
        self.assertFalse(result["strict_accepted"])


if __name__ == "__main__":
    unittest.main()
