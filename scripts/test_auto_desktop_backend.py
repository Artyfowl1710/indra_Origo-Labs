"""Exercise the running desktop's authenticated chat/attachment protocol."""
import argparse
import base64
import io
import json
from pathlib import Path
import re
import secrets
import tempfile
import time
from urllib.parse import urlsplit, quote

import httpx
from PIL import Image, ImageDraw, ImageFont
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]


def run(origin, workspace_only=False):
    parsed = urlsplit(origin)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port or parsed.path not in {"", "/"}:
        raise ValueError("Use the running desktop's loopback origin")
    html = httpx.get(origin + "/chat", timeout=10, trust_env=False).text
    match = re.search(r'window\.__HERMES_SESSION_TOKEN__\s*=\s*("(?:\\.|[^"\\])*")', html)
    if not match:
        raise RuntimeError("Loopback session token was not present in the served page")
    token = json.loads(match.group(1))
    rows, event_buffer = [], []
    output = ROOT / "data/test-results"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="desktop-file-", dir=output) as fixture_dir, connect(origin.replace("http://", "ws://") + "/api/ws?token=" + quote(token),
                 origin=origin, open_timeout=15, max_size=8 * 1024 * 1024) as ws:
        counter = 0
        def rpc(method, params):
            nonlocal counter
            counter += 1
            request_id = "origo-probe-" + str(counter)
            ws.send(json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}))
            while True:
                row = json.loads(ws.recv(timeout=120))
                if row.get("id") == request_id:
                    if "error" in row:
                        raise RuntimeError("Desktop RPC rejected " + method)
                    return row.get("result", {})
                event_buffer.append(row)

        session = rpc("session.create", {"source": "dashboard", "cwd": fixture_dir, "hidden": True})["session_id"]
        verification = "ORIGO_" + secrets.token_hex(8).upper()
        fixture = Path(fixture_dir) / "verification.txt"
        fixture.write_text(verification + "\n", encoding="utf-8")
        image = Image.new("RGB", (280, 120), "white")
        ImageDraw.Draw(image).text((20, 30), "INDRA42", fill="black", font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 48))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        cases = [("greeting", "hi")]
        if workspace_only:
            cases += [("file-after-greeting", f"Use read_file to read {fixture.as_posix()} and return the exact verification code inside. Do not change any files."),
                      ("thanks", "thanks")]
        else:
            cases += [("attached-image", "What alphanumeric identifier is printed in the image? Reply only with the exact text, preserving capitalization.")]
        for name, prompt in cases:
            print("Starting desktop", name, flush=True)
            event_buffer.clear()
            if name == "attached-image":
                rpc("image.attach_bytes", {"session_id": session, "filename": "origo-synthetic.png",
                                           "content_base64": base64.b64encode(buffer.getvalue()).decode()})
            started = time.monotonic()
            rpc("prompt.submit", {"session_id": session, "text": prompt})
            tools, answer, error = [], "", None
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                row = event_buffer.pop(0) if event_buffer else json.loads(ws.recv(timeout=300))
                event = row.get("params", {}) if row.get("method") == "event" else {}
                if event.get("session_id") != session:
                    continue
                payload = event.get("payload", {})
                if event.get("type") == "tool.start":
                    tools.append(payload.get("name"))
                if event.get("type") == "message.complete":
                    answer = payload.get("text", "")
                    break
                if event.get("type") == "error":
                    error = payload.get("message") or payload.get("text") or "Desktop error"
                    break
            row = {"case": name, "answer": answer, "tools": tools, "error": error,
                   "seconds": round(time.monotonic() - started, 2),
                   "passed": bool(answer) and not error and (
                       not tools if name in {"greeting", "thanks"} else
                       verification in answer and "read_file" in tools if name == "file-after-greeting" else
                       "INDRA42" in answer)}
            rows.append(row)
            print(json.dumps(row), flush=True)
    destination = output / ("desktop-workspace-sequence.json" if workspace_only else "automatic-desktop-backend.json")
    destination.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    if len(rows) != len(cases) or not all(row["passed"] for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", required=True)
    parser.add_argument("--workspace-only", action="store_true", help="Test hi → real file read → thanks in one session")
    args = parser.parse_args()
    run(args.origin.rstrip("/"), workspace_only=args.workspace_only)
