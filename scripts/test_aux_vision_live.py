"""Exercise the real local vision tool fallback without a cloud request or user files."""
import asyncio
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.parse import urlsplit

from dotenv import dotenv_values
from PIL import Image, ImageDraw, ImageFont
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "indra/SIH-26/hermes-agent"))


def run():
    active = ROOT / "data/indra-auto-home"
    config = yaml.safe_load((active / "config.yaml").read_text(encoding="utf-8"))
    local = config["providers"]["origo-local"]
    origin = local["base_url"]
    parsed = urlsplit(origin)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port or parsed.path != "/v1":
        raise ValueError("Expected the active local routing endpoint")
    key = dotenv_values(active / ".env").get("ORIGO_LOCAL_INFERENCE_KEY")
    if not key: raise ValueError("Missing local routing credential")
    output = ROOT / "data/test-results"
    with tempfile.TemporaryDirectory(prefix="aux-vision-", dir=output) as directory:
        home = Path(directory)
        cfg = {"model": {"provider": "custom", "default": "synthetic-text-only", "supports_vision": False},
               "terminal": {"backend": "local", "cwd": str(home)}, "agent": {"image_input_mode": "auto"},
               "auxiliary": {"vision": {"provider": "custom", "model": "origo-auto", "base_url": origin,
                                          "key_env": "ORIGO_LOCAL_INFERENCE_KEY", "timeout": 180}}}
        (home / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
        os.environ["HERMES_HOME"] = str(home)
        from agent.secret_scope import set_secret_scope, reset_secret_scope
        scope = set_secret_scope({"ORIGO_LOCAL_INFERENCE_KEY": key})
        try:
            from tools.vision_tools import vision_analyze_tool
            image = Image.new("RGB", (280, 120), "white")
            ImageDraw.Draw(image).text((20, 30), "INDRA42", fill="black", font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 48))
            source = home / "fixture.png"; image.save(source)
            started = time.monotonic()
            print("Testing local OCR fallback through vision_analyze", flush=True)
            result = json.loads(asyncio.run(vision_analyze_tool(str(source), "Read the identifier printed in this image. Return only its text.")))
            passed = bool(result.get("success")) and bool(re.search(r"\bINDRA42\b", str(result.get("analysis", "")).upper()))
            report = {"case": "text-only-main-local-vision-tool", "passed": passed,
                      "seconds": round(time.monotonic() - started, 2), "local_only": True,
                      "error": str(result.get("error", ""))[:250]}
            (output / "aux-vision-live.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report), flush=True)
            if not passed: raise SystemExit(1)
        finally:
            reset_secret_scope(scope)


if __name__ == "__main__": run()
