"""Launch the real native app/backend with missing assets and an engine startup failure."""
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.parse import urlsplit
import uuid

ROOT = Path(__file__).resolve().parents[1]
ELECTRON = ROOT / "indra/SIH-26/hermes-agent/apps/desktop/node_modules/electron/dist/electron.exe"
OUTPUT = ROOT / "data/test-results"


def run(case):
    home = OUTPUT / ("startup-preview-" + uuid.uuid4().hex)
    home.mkdir(parents=True)
    # A valid fixture route, never contacted: startup must not change the selection
    # or require the provider to be online in order to show the desktop.
    (home / "config.yaml").write_text(json.dumps({
        "model": {"provider": "custom", "default": "saved-cloud-fixture",
                  "base_url": "http://127.0.0.1:1/v1"},
        "security": {"untrusted_content_guard": True},
        "terminal": {"backend": "docker", "cwd": str(home)},
        "fallback_model": None,
    }), encoding="utf-8")
    env = {key:value for key,value in os.environ.items()
           if key.upper() in {"PATH","SYSTEMROOT","WINDIR","USERPROFILE","APPDATA",
                              "LOCALAPPDATA","TEMP","TMP","COMSPEC","PROGRAMFILES","PROGRAMFILES(X86)"}}
    env.update({
        "ORIGO_HOME": str(home), "ORIGO_DESKTOP_USER_DATA": str(home / "desktop"),
        "HERMES_HOME": str(home), "HERMES_DESKTOP": "1", "PYTHONUTF8": "1",
        "ORIGO_AUTO_ROUTING": "0" if case == "models-missing" else "1",
        "ORIGO_LOCAL_STARTUP_ISSUE": "models-missing" if case == "models-missing" else "",
        "ORIGO_EXPECT_STARTUP_ISSUE": case,
        "ORIGO_RUNTIME_DIR": str(home / "missing-runtime"),
        "ORIGO_MODEL_DIR": str(home / "missing-models"),
        # The router is lazy: missing weights alone do not make its HTTP process
        # exit. An invalid device argument exercises a real startup-process failure.
        "ORIGO_DEVICE": "invalid-fixture" if case == "service-failed" else "auto",
    })
    with (home / "electron.log").open("w", encoding="utf-8") as log:
        result = subprocess.run([str(ELECTRON), str(ROOT / "origo-desktop/startup-preview.cjs")],
                                cwd=ROOT, env=env, stdout=log, stderr=log, timeout=115)
    report = json.loads((home / "acceptance.json").read_text(encoding="utf-8"))
    if result.returncode or report["error"] or not all(row["passed"] for row in report["checks"]):
        raise RuntimeError(f"{case} startup failed; inspect {home / 'acceptance.json'}")
    # The app owns and stops its backend; closing the fixture must release the port.
    port = urlsplit(report["origin"]).port
    for _ in range(30):
        with socket.socket() as probe:
            probe.settimeout(.2)
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                report["checks"].append({"name": "owned backend stopped on app exit", "passed": True})
                break
        time.sleep(.1)
    else:
        raise RuntimeError("Fixture backend remained listening after its app exited")
    report["case"] = case
    (home / "acceptance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"case": case, "checks": len(report["checks"]), "report": str(home / "acceptance.json")}),
          flush=True)
    return report


if __name__ == "__main__":
    reports = [run(case) for case in ("models-missing", "service-failed")]
    (OUTPUT / "optional-local-startup-acceptance.json").write_text(
        json.dumps(reports, indent=2), encoding="utf-8")
