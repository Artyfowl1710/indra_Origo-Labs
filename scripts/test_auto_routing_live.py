"""Real signed-runtime acceptance probe; no cloud calls or credentials."""
import argparse
import asyncio
import base64
import io
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
from PIL import Image, ImageDraw, ImageFont
from origo_runtime.gateway import create_app
from origo_runtime.llamacpp import LlamaRuntime
from origo_runtime.image_input import add_evidence


async def run(device):
    runtime = LlamaRuntime(Path(os.environ["LOCALAPPDATA"]) / "Programs/Ollama/lib/ollama",
                          Path(r"C:\Users\khatr\OneDrive\Desktop\SIH-26-main\SIH-26\hermes-agent\backend\models"),
                          ROOT / "logs", device)
    token = "live-test-local-only-" * 3
    app = create_app(runtime, token)
    image = Image.new("RGB", (280, 120), "white")
    ImageDraw.Draw(image).text((20, 30), "INDRA42", fill="black", font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 48))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    rows = []
    def inspect_synthetic_evidence(messages, evidence):
        print(json.dumps({"synthetic_image_observation": evidence}), flush=True)
        return add_evidence(messages, evidence)
    async def probe():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://origo",
                                     headers={"Authorization": "Bearer " + token}, timeout=600) as client:
            for name, content, expected in [
                ("image-auto", [{"type": "text", "text": "What alphanumeric identifier is printed in the image? Reply only with the exact text, preserving capitalization."},
                                {"type": "image_url", "image_url": {"url": url}}], "INDRA42"),
                ("return-to-text", "Reply only with TEXT_OK", "TEXT_OK"),
            ]:
                print("Starting", name, device, flush=True)
                started = time.monotonic()
                response = await client.post("/v1/chat/completions", json={"model": "origo-auto", "messages": [
                    {"role": "user", "content": content}], "max_tokens": 64, "temperature": 0})
                body = response.json()
                answer = body.get("choices", [{}])[0].get("message", {}).get("content", "")
                health = (await client.get("/health")).json()
                row = {"case": name, "http": response.status_code, "passed": expected in str(answer),
                       "answer": answer, "seconds": round(time.monotonic() - started, 2), "runtime": health}
                rows.append(row)
                print(json.dumps(row), flush=True)

    try:
        with patch("origo_runtime.gateway.add_evidence", inspect_synthetic_evidence):
            await probe()
    finally:
        await runtime.stop()
        destination = ROOT / "data/test-results" / f"automatic-routing-{device}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    if len(rows) != 2 or not all(row["passed"] for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", choices=["cpu", "gpu", "auto"], default="auto")
    asyncio.run(run(parser.parse_args().device))
