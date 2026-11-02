"""Exercise unpinned cloud image routing and native video tool forwarding."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "indra/SIH-26/hermes-agent"))

def run():
    active = ROOT / "data/indra-auto-home"
    os.environ["HERMES_HOME"] = str(active)
    from hermes_cli.gemini_catalog import credentials
    key, base = credentials()
    if not key: raise RuntimeError("No saved Google credential")
    from hermes_cli.model_modalities import choose
    expected = choose("gemini", "synthetic-text-only", {"image"})
    output = ROOT / "data/test-results"
    cases = []
    with tempfile.TemporaryDirectory(prefix="cloud-routing-", dir=output, ignore_cleanup_errors=True) as directory:
        home = Path(directory)
        (home / "cache").mkdir()
        shutil.copyfile(active / "cache/gemini-live-models.json", home / "cache/gemini-live-models.json")
        cfg = {"model": {"provider": "gemini", "default": "synthetic-text-only", "supports_vision": False},
               "auxiliary": {"vision": {"provider": "auto"}}, "terminal": {"cwd": str(home), "backend": "local"}}
        (home / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
        os.environ["HERMES_HOME"] = str(home)
        from agent.auxiliary_client import scoped_runtime_main
        from tools.vision_tools import vision_analyze_tool, video_analyze_tool, _video_route_kwargs
        image = Image.new("RGB", (280,120), "white")
        ImageDraw.Draw(image).text((20,30), "INDRA42", fill="black", font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf",48))
        image_path = home / "identifier.png"; image.save(image_path)
        runtime = {"provider": "gemini", "model": "synthetic-text-only", "api_key": key, "base_url": base}
        with scoped_runtime_main(runtime):
            result = json.loads(asyncio.run(vision_analyze_tool(str(image_path), "Return only the identifier printed in this image.")))
        cases.append({"case": "automatic-cheapest-image-reader", "initial_candidate": expected["model"], "routing": result.get("routing"), "reason": expected["reason"],
                      "passed": bool(result.get("success")) and "INDRA42" in str(result.get("analysis", "")).upper()})
        video_path = home / "blue.mp4"
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg: raise RuntimeError("ffmpeg required for synthetic video fixture")
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=blue:s=160x120:d=1", "-pix_fmt", "yuv420p", str(video_path)], check=True, capture_output=True)
        runtime["model"] = "gemini-3.5-flash-lite"
        with scoped_runtime_main(runtime):
            route = _video_route_kwargs(None)
            result = json.loads(asyncio.run(video_analyze_tool(str(video_path), "What single color fills this video? Answer with just the color.")))
        cases.append({"case": "video-tool-keeps-capable-main", "model": route["model"], "passed": bool(result.get("success")) and "blue" in str(result.get("analysis", "")).lower()})
    (output / "cloud-routing-live.json").write_text(json.dumps(cases, indent=2), encoding="utf-8")
    print(json.dumps(cases), flush=True)
    return all(case["passed"] for case in cases)

if __name__ == "__main__": raise SystemExit(0 if run() else 1)
