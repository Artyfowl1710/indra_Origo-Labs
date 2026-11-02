"""Owned, signed llama.cpp process lifecycle. Never starts a host shell tool."""
import asyncio
from contextlib import suppress
import os
from pathlib import Path
import socket
import subprocess
import time

import httpx
from .process_lifetime import require_owned_process_tree, contain_owned_child

MODELS = {
    "text": ("Qwen3.5-4B-Q4_K_M.gguf", "origo-qwen35", 16384),
    "vision": ("Qwen2-VL-OCR-2B-Instruct.Q4_K_M.gguf", "origo-vision", 8192),
}
PROJECTOR = "mmproj-Qwen2-VL-2B-Instruct-f16.gguf"


class LlamaRuntime:
    def __init__(self, runtime_dir: Path, model_dir: Path, log_dir: Path, device="auto"):
        if device not in {"auto", "cpu", "gpu"}:
            raise ValueError("device must be auto, cpu or gpu")
        self.runtime_dir = runtime_dir.resolve()
        self.model_dir = model_dir.resolve()
        self.log_dir = log_dir
        self.device = device
        self.active_device = None
        self.process = None
        self.route = None
        self.origin = None
        self._verified = None
        self.last_load_seconds = None

    async def verify(self):
        server = self.runtime_dir / "llama-server.exe"
        stamp = (server.stat().st_size, server.stat().st_mtime_ns)
        if stamp == self._verified:
            return
        if os.name != "nt":
            raise RuntimeError("This runtime adapter requires the signed Windows distribution")
        # The path is carried in the child environment, never interpolated as code.
        env = {**os.environ, "ORIGO_VERIFY_BINARY": str(server)}
        # PowerShell 7's inherited module path can break module loading in
        # Windows PowerShell 5.1. Let the verifier initialize its own defaults.
        env = {key: value for key, value in env.items() if key.casefold() != "psmodulepath"}
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        command = "$s=Get-AuthenticodeSignature -LiteralPath $env:ORIGO_VERIFY_BINARY; if($s.Status -ne 'Valid'){exit 1}; $s.SignerCertificate.Subject"
        process = await asyncio.create_subprocess_exec(
            str(powershell), "-NoProfile", "-NonInteractive", "-Command", command,
            env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), 20)
        except BaseException:
            if process.returncode is None:
                process.kill()
            await process.wait()
            raise
        if process.returncode != 0 or "Ollama" not in output.decode(errors="replace"):
            raise RuntimeError("A valid Ollama-signed inference runtime is required")
        self._verified = stamp

    async def stop(self):
        owned, self.process = self.process, None
        self.route = self.origin = None
        self.active_device = None
        if owned and owned.returncode is None:
            with suppress(ProcessLookupError):
                owned.terminate()
            try:
                await asyncio.wait_for(owned.wait(), 10)
            except asyncio.TimeoutError:
                with suppress(ProcessLookupError):
                    owned.kill()
                await owned.wait()

    async def ensure(self, route):
        if route not in MODELS:
            raise ValueError("Unknown inference route")
        if self.route == route and self.process and self.process.returncode is None:
            return self.origin
        filename, alias, context = MODELS[route]
        model = self.model_dir / filename
        if not model.is_file() or (route == "vision" and not (self.model_dir / PROJECTOR).is_file()):
            raise FileNotFoundError(f"Missing model or projector for {route}")
        await self.verify()
        await self.stop()
        devices = ["gpu", "cpu"] if self.device == "auto" else [self.device]
        if not (self.runtime_dir / "cuda_v13/ggml-cuda.dll").is_file():
            devices = ["cpu"] if self.device == "auto" else devices
        last_error = None
        for device in devices:
            try:
                await self._start(route, model, alias, context, device)
                return self.origin
            except asyncio.CancelledError:
                await self.stop()
                raise
            except (RuntimeError, OSError, asyncio.TimeoutError) as exc:
                last_error = exc
                await self.stop()
        raise RuntimeError(f"Inference startup failed ({last_error}); inspect runtime logs")

    async def _start(self, route, model, alias, context, device):
        require_owned_process_tree()
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env = os.environ.copy()
        cuda = self.runtime_dir / "cuda_v13"
        if device == "gpu":
            env["GGML_BACKEND_PATH"] = str(cuda / "ggml-cuda.dll")
            env["PATH"] = str(cuda) + os.pathsep + env["PATH"]
        else:
            env.pop("GGML_BACKEND_PATH", None)
        args = [str(self.runtime_dir / "llama-server.exe"), "--model", str(model),
                "--alias", alias, "--host", "127.0.0.1", "--port", str(port),
                "--n-gpu-layers", "99" if device == "gpu" else "0", "--ctx-size", str(context),
                "--batch-size", "128", "--ubatch-size", "64", "--parallel", "1", "--threads", "8",
                "--no-warmup", "--jinja", "--reasoning", "off"]
        if route == "vision":
            args.extend(["--mmproj", str(self.model_dir / PROJECTOR)])
            if device == "cpu":
                args.append("--no-mmproj-offload")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        with (self.log_dir / f"routing-{route}.log").open("ab") as log:
            self.process = await asyncio.create_subprocess_exec(
                *args, env=env, stdout=log, stderr=log,
                **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}),
            )
        try:
            contain_owned_child(self.process)
        except BaseException:
            await self.stop()
            raise
        origin = f"http://127.0.0.1:{port}"
        async with httpx.AsyncClient(timeout=1, trust_env=False) as client:
            for _ in range(180):
                if self.process.returncode is not None:
                    raise RuntimeError(f"{device} runtime exited ({self.process.returncode})")
                try:
                    response = await client.get(origin + "/health")
                    if response.status_code == 200:
                        self.origin, self.route, self.active_device = origin, route, device
                        self.last_load_seconds = round(time.monotonic() - started, 3)
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(.5)
        raise RuntimeError("Model startup timed out")
