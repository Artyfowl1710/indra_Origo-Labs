"""Probe one OpenAI-compatible inference call and inspect a synthetic tool call.

The probe function is deliberately never executed; the script only checks the model's
response. No project files are included in the prompt.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", encoding="utf-8-sig")

from app.providers import OpenAICompatibleProvider  # noqa: E402

TOOL = [{"type": "function", "function": {
    "name": "indra_harness_probe",
    "description": "A harmless capability test with no side effects. Do not execute it.",
    "parameters": {"type": "object", "properties": {"status": {"type": "string", "enum": ["ok"]}},
                    "required": ["status"], "additionalProperties": False},
}}]


async def main() -> int:
    provider = OpenAICompatibleProvider()
    start = time.perf_counter()
    try:
        timeout = max(5, min(float(os.getenv("INDRA_SMOKE_TIMEOUT", "45")), 120))
        print(f"Endpoint: {provider.display_endpoint}\nConfigured model: {provider.model}")
        response = await asyncio.wait_for(provider.chat([
            {"role": "system", "content": "You are testing an API. This synthetic probe has no side effects; no real tools are available."},
            {"role": "user", "content": "Call indra_harness_probe once with status=ok. If tool calling is unavailable, respond briefly in text."},
        ], tools=TOOL, max_tokens=64), timeout=timeout)
        calls = response.get("tool_calls") or []
        detected = any(isinstance(call, dict) and isinstance(call.get("function"), dict)
                       and call["function"].get("name") == "indra_harness_probe" for call in calls)
        text = response.get("content") or ""
        elapsed = round((time.perf_counter() - start) * 1000)
        print(f"Elapsed: {elapsed} ms")
        print(f"Text generation: {'OK' if text or detected else 'NO OUTPUT'}")
        print(f"Tool-call response: {'DETECTED (not executed)' if detected else 'NOT DETECTED'}")
        if text:
            print("Response preview:", str(text)[:300].replace("\n", " "))
        if detected:
            return 0
        print("The model endpoint responded, but the harness cannot verify tool-calling compatibility for this model/chat template.")
        return 2 if text else 1
    except asyncio.TimeoutError:
        print("Timed out. Check whether the model is still loading and inspect the inference server log.", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Inference check failed safely ({type(exc).__name__}). Check the endpoint, model alias and local server log.", file=sys.stderr)
        return 1
    finally:
        await provider.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
