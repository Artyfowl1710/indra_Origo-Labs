"""Real loopback dashboard auth probe using an isolated phone-sharing profile.

Does not publish a Tailscale route or modify the user's active profile.
"""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
import yaml
from websockets.sync.client import connect
from websockets.exceptions import InvalidStatus
from origo_runtime.phone_config import save_settings, apply_settings


def run():
    output = ROOT / "data/test-results"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    def record(case, passed):
        row = {"case": case, "passed": bool(passed)}
        rows.append(row)
        print(json.dumps(row), flush=True)
        if not passed:
            raise RuntimeError("Phone authentication check failed: " + case)
    with tempfile.TemporaryDirectory(prefix="phone-auth-", dir=output) as directory:
        home = Path(directory)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        payload = {"endpoint": "https://origo.phone-fixture.ts.net", "username": "origo-fixture",
                   "password": secrets.token_urlsafe(24), "port": port}
        env = {key: value for key, value in os.environ.items() if key not in {"HERMES_DESKTOP", "HERMES_DASHBOARD_SESSION_TOKEN", "HERMES_DASHBOARD_PUBLIC_URL"}
               and not key.startswith("HERMES_DASHBOARD_BASIC_AUTH_")}
        env.update({"HERMES_HOME": str(home), "PYTHONUTF8": "1"})
        process = None
        def configure():
            save_settings(home, payload)
            config = apply_settings(home, {"model": {"provider": "custom", "default": "fixture-model",
                                                    "base_url": "http://127.0.0.1:9/v1", "api_key": "local-fixture"}})
            (home / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
        def stop():
            nonlocal process
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        def start():
            nonlocal process
            with (output / "phone-auth-server.log").open("ab") as log:
                process = subprocess.Popen([sys.executable, "-m", "hermes_cli.main", "dashboard", "--no-open", "--skip-build",
                                            "--host", "127.0.0.1", "--port", str(port)],
                                           cwd=ROOT / "indra/SIH-26/hermes-agent", env=env, stdout=log, stderr=log,
                                           **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
            for _ in range(120):
                if process.poll() is not None:
                    raise RuntimeError("Fixture dashboard exited; inspect phone-auth-server.log")
                try:
                    if httpx.get(origin + "/login", timeout=1, trust_env=False).status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                time.sleep(.5)
            raise RuntimeError("Fixture dashboard startup timed out")
        try:
            configure()
            print("Starting isolated gated dashboard", flush=True)
            start()
            with httpx.Client(base_url=origin, trust_env=False, timeout=10, follow_redirects=False) as client:
                record("loopback-protected", client.get("/api/config").status_code == 401)
                record("public-host-protected", client.get("/api/config", headers={"Host": "origo.phone-fixture.ts.net"}).status_code == 401)
                login = {"provider": "basic", "username": payload["username"], "password": "wrong-fixture-password", "next": "/chat"}
                record("wrong-password-rejected", client.post("/auth/password-login", json=login).status_code == 401)
                login["password"] = payload["password"]
                record("password-login", client.post("/auth/password-login", json=login).status_code == 200)
                record("session-authenticated", client.get("/api/auth/me").status_code == 200)
                ticket = client.post("/api/auth/ws-ticket").json()["ticket"]
                with connect(origin.replace("http://", "ws://") + "/api/ws?ticket=" + ticket, origin=origin, open_timeout=5):
                    record("websocket-ticket-accepted", True)
                try:
                    with connect(origin.replace("http://", "ws://") + "/api/ws?ticket=" + ticket, origin=origin, open_timeout=5):
                        record("websocket-ticket-single-use", False)
                except InvalidStatus:
                    record("websocket-ticket-single-use", True)
                cookies = httpx.Cookies(client.cookies)
            stop()
            configure()
            print("Restarting with rotated session-signing key", flush=True)
            start()
            with httpx.Client(base_url=origin, trust_env=False, cookies=cookies, timeout=10) as client:
                record("old-session-revoked-after-rotation", client.get("/api/auth/me").status_code == 401)
                record("password-login-after-rotation", client.post("/auth/password-login", json=login).status_code == 200)
        finally:
            stop()
            (output / "phone-auth-live.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    run()
