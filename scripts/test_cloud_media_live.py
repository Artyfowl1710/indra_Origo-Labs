"""Small real Google vision checks using saved credentials and synthetic data only."""
import asyncio
import base64
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "indra/SIH-26/hermes-agent"))

def run():
    os.environ["HERMES_HOME"] = str(ROOT / "data/indra-auto-home")
    from hermes_cli.gemini_catalog import credentials, models
    key, base = credentials()
    if not key: raise RuntimeError("No saved Google credential")
    catalog = models(refresh=True)
    if not catalog: raise RuntimeError("Google discovery returned no models")
    from hermes_cli.model_modalities import choose
    target = "gemini-3.5-flash-lite"
    image = Image.new("RGB", (280, 120), "white")
    ImageDraw.Draw(image).text((20, 30), "INDRA42", fill="black", font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 48))
    buffer = io.BytesIO(); image.save(buffer, format="PNG")
    content = [{"type": "text", "text": "Read the identifier in the image. Return only the identifier."},
               {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()}}]
    output = ROOT / "data/test-results"; output.mkdir(exist_ok=True)
    report = {"catalog_count": len(catalog), "cases": []}
    # The agent receives a multimodal main, with a deliberately unavailable local reader.
    # A successful answer proves auto mode retained native media rather than calling that reader.
    with tempfile.TemporaryDirectory(prefix="cloud-media-", dir=output, ignore_cleanup_errors=True) as directory:
        home = Path(directory)
        config = {"model": {"provider": "gemini", "default": target}, "agent": {"image_input_mode": "auto"},
                  "auxiliary": {"vision": {"provider": "custom", "model": "unavailable-local-reader", "base_url": "http://127.0.0.1:1/v1"}},
                  "terminal": {"backend": "local", "cwd": str(home)}}
        (home / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
        os.environ["HERMES_HOME"] = str(home)
        from agent.image_routing import decide_image_input_mode
        from run_agent import AIAgent
        started = time.monotonic()
        try:
            mode = decide_image_input_mode("gemini", target, config)
            if mode != "native": raise RuntimeError("Expected native image route")
            agent = AIAgent(provider="gemini", model=target, api_key=key, base_url=base,
                            max_iterations=2, enabled_toolsets=[], skip_context_files=True, skip_memory=True,
                            skip_background_review=True, quiet_mode=True, max_tokens=256)
            result = agent.run_conversation(content, system_message="Read the supplied synthetic test image. Reply concisely.")
            answer = str(result.get("final_response", ""))
            report["cases"].append({"case": "native-agent-ignores-unneeded-local-reader", "model": target, "mode": mode,
                                     "passed": "INDRA42" in answer.upper(), "seconds": round(time.monotonic()-started,2)})
            agent.close()
        except Exception as exc:
            # Only bounded classification is recorded, never a request URL containing credentials.
            report["cases"].append({"case": "native-agent", "passed": False, "error_type": type(exc).__name__, "status": getattr(exc, "status_code", None)})
        # Test the real auxiliary client path for a text-only selected main.
        config["auxiliary"] = {"vision": {"provider": "auto"}}
        (home / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
        os.environ["HERMES_HOME"] = str(ROOT / "data/indra-auto-home")
        route = choose("gemini", "synthetic-text-only", {"image"}, explicit_model=target)
        from agent.auxiliary_client import resolve_vision_provider_client, scoped_runtime_main
        try:
            with scoped_runtime_main({"provider": "gemini", "model": "synthetic-text-only", "api_key": key, "base_url": base}):
                _, client, selected = resolve_vision_provider_client(model=route["model"], provider="gemini", api_key=key, base_url=base)
                response = client.chat.completions.create(model=selected, messages=[{"role": "user", "content": content}], max_tokens=128)
                answer = str(response.choices[0].message.content)
                report["cases"].append({"case": "cloud-auxiliary-vision-reader", "model": selected, "passed": "INDRA42" in answer.upper()})
        except Exception as exc:
            report["cases"].append({"case": "cloud-auxiliary-vision-reader", "passed": False, "error_type": type(exc).__name__, "status": getattr(exc,"status_code", None)})
    (output / "cloud-media-live.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)
    return all(case["passed"] for case in report["cases"])

if __name__ == "__main__": raise SystemExit(0 if run() else 1)
