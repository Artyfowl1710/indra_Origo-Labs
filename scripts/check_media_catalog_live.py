"""Read-only check of the running desktop's actual model-picker response."""
import json
from pathlib import Path
import re
import sys
import httpx

def run(origin):
    from urllib.parse import urlsplit
    parts = urlsplit(origin)
    if parts.scheme != "http" or parts.hostname != "127.0.0.1" or not parts.port: raise ValueError("Expected loopback origin")
    with httpx.Client(base_url=origin, timeout=180, trust_env=False) as client:
        html = client.get("/chat").text
        match = re.search(r'window\.__HERMES_SESSION_TOKEN__\s*=\s*("(?:\\.|[^"\\])*")', html)
        if not match: raise RuntimeError("No desktop session token")
        client.headers["X-Hermes-Session-Token"] = json.loads(match.group(1))
        response = client.get("/api/model/options?include_unconfigured=1&refresh=1")
        response.raise_for_status()
        rows = response.json().get("providers", [])
        google = next(p for p in rows if p["slug"] == "gemini")
        ids = google.get("models", [])
        report = {"google_count": len(ids), "models": ids, "google_3_8_tts": google.get("capabilities", {}).get("gemini-3.8-flash-tts"),
                  "google_3_8_flash": google.get("capabilities", {}).get("gemini-3.8-flash")}
        output = Path(__file__).resolve().parents[1] / "data/test-results/media-catalog-desktop.json"
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"count": len(ids), "has_tts": "gemini-3.8-flash-tts" in ids, "tts_kind": (report["google_3_8_tts"] or {}).get("model_kind")}))

if __name__ == "__main__": run(sys.argv[1])
