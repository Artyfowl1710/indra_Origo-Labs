"""One-shot OpenRouter compatibility check. Reads a key without echo, never a file."""
import asyncio
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.providers import OpenAICompatibleProvider, ProviderError

MODEL = "dots-studio/dots-3-note-preview:free"


async def main() -> int:
    key = getpass.getpass("Temporary OpenRouter key: ").strip()
    if not key:
        print("No key supplied.")
        return 2
    os.environ["INDRA_HOSTED_BASE_URL"] = "https://openrouter.ai/api/v1"
    os.environ["INDRA_HOSTED_API_KEY"] = key
    os.environ["INDRA_HOSTED_MODEL"] = MODEL
    provider = OpenAICompatibleProvider()
    try:
        provider.use_profile("hosted")
        models = await provider.list_models(force=True)
        if MODEL not in models:
            print("Requested model is not advertised by OpenRouter.")
            return 1
        result = await provider.chat(
            [{"role": "user", "content": "Reply with exactly ORIGO_OK."}], max_tokens=24
        )
        answer = str(result.get("content") or "").strip()
        print(f"model={provider._resolved_model or provider.model} advertised=yes answer={answer[:80]!r}")
        return 0 if "ORIGO_OK" in answer else 1
    except ProviderError as exc:
        print(f"Provider check failed: {exc}")
        return 1
    finally:
        await provider.aclose()
        os.environ.pop("INDRA_HOSTED_API_KEY", None)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
