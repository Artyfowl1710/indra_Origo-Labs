"""Force-kill an isolated signed CPU model owner and verify kernel cleanup."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import httpx
import psutil

ROOT = Path(__file__).resolve().parents[1]


def alive(row):
    try:
        process = psutil.Process(row["pid"])
        return process.is_running() and abs(process.create_time() - row["created"]) < .01
    except psutil.NoSuchProcess:
        return False


def run(models):
    output = ROOT / "data/test-results"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="model-crash-", dir=output) as directory:
        directory = Path(directory)
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        children, receipt, control = [], None, None
        started = time.monotonic()
        try:
            control_launcher = subprocess.Popen([sys.executable, "-u", str(ROOT / "scripts/job_lifetime_fixture.py"), "control", str(directory)],
                                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
            children.append(control_launcher)
            with (output / "model-crash-live.log").open("wb") as log:
                owner = subprocess.Popen([sys.executable, "-u", str(ROOT / "scripts/model_crash_fixture.py"),
                                          "--directory", str(directory), "--models", str(models)],
                                         stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=flags)
                children.append(owner)
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if owner.poll() is not None:
                    raise RuntimeError("The isolated model owner exited; inspect model-crash-live.log")
                if (directory / "model-ready.json").exists() and (directory / "control.json").exists():
                    receipt = json.loads((directory / "model-ready.json").read_text())
                    control = json.loads((directory / "control.json").read_text())
                    break
                time.sleep(.2)
            if receipt is None:
                raise RuntimeError("The isolated model did not become ready")
            httpx.get(receipt["origin"] + "/health", timeout=3, trust_env=False).raise_for_status()
            if not alive(receipt["owner"]):
                raise RuntimeError("Model owner identity changed")
            psutil.Process(receipt["owner"]["pid"]).kill()
            deadline = time.monotonic() + 10
            while alive(receipt["server"]) and time.monotonic() < deadline:
                time.sleep(.1)
            reachable = False
            try:
                reachable = httpx.get(receipt["origin"] + "/health", timeout=1, trust_env=False).status_code == 200
            except httpx.HTTPError:
                pass
            result = {"case": "signed-cpu-model-owner-crash", "device": receipt["device"],
                      "owned_server_reaped": not alive(receipt["server"]), "health_endpoint_closed": not reachable,
                      "unrelated_process_survived": alive(control), "seconds": round(time.monotonic() - started, 2)}
            result["passed"] = result["owned_server_reaped"] and result["health_endpoint_closed"] and result["unrelated_process_survived"]
            (output / "model-crash-live.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result), flush=True)
            if not result["passed"]:
                raise SystemExit(1)
        finally:
            if receipt:
                for row in (receipt["server"], receipt["owner"]):
                    if alive(row):
                        process = psutil.Process(row["pid"]); process.kill(); process.wait(timeout=10)
            if control is None and (directory / "control.json").exists():
                control = json.loads((directory / "control.json").read_text())
            if control and alive(control):
                process = psutil.Process(control["pid"]); process.kill(); process.wait(timeout=10)
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, default=Path(r"C:\Users\khatr\OneDrive\Desktop\SIH-26-main\SIH-26\hermes-agent\backend\models"))
    run(parser.parse_args().models)
