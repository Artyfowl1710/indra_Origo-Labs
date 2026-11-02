"""Disposable CPU llama.cpp owner for crash-lifecycle acceptance."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import psutil
from origo_runtime.llamacpp import LlamaRuntime


async def run(directory, models):
    runtime = LlamaRuntime(Path(os.environ["LOCALAPPDATA"]) / "Programs/Ollama/lib/ollama", models,
                           directory / "logs", "cpu")
    try:
        origin = await runtime.ensure("text")
        row = {"owner": {"pid": os.getpid(), "created": psutil.Process().create_time()},
               "server": {"pid": runtime.process.pid, "created": psutil.Process(runtime.process.pid).create_time()},
               "origin": origin, "device": runtime.active_device}
        temporary = directory / "model-ready.tmp"
        temporary.write_text(json.dumps(row), encoding="utf-8")
        os.replace(temporary, directory / "model-ready.json")
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            await asyncio.sleep(.2)
    finally:
        await runtime.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.directory.resolve(), args.models.resolve()))
