import argparse
import asyncio
import os
from pathlib import Path

import uvicorn
from .gateway import create_app
from .llamacpp import LlamaRuntime


def main():
    parser = argparse.ArgumentParser(description="Origo local multimodal inference gateway")
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--device", choices=["auto", "gpu", "cpu"], default="auto")
    parser.add_argument("--parent-pid", type=int)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    root = Path(__file__).resolve().parents[1]
    runtime = LlamaRuntime(args.runtime, args.models, root / "logs", args.device)
    app = create_app(runtime, os.environ.get("ORIGO_ROUTER_TOKEN", ""))
    async def serve():
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port,
                                             access_log=False, timeout_graceful_shutdown=5))
        async def watch_parent():
            import psutil
            try:
                parent = psutil.Process(args.parent_pid)
                born = parent.create_time()
            except psutil.Error:
                server.should_exit = True
                return
            while not server.should_exit:
                try:
                    if not parent.is_running() or parent.create_time() != born:
                        break
                except psutil.Error:
                    break
                await asyncio.sleep(1)
            server.should_exit = True
        watcher = asyncio.create_task(watch_parent()) if args.parent_pid else None
        try:
            await server.serve()
        finally:
            if watcher:
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
            await runtime.stop()
    asyncio.run(serve())


if __name__ == "__main__":
    main()
