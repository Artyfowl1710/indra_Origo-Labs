"""Own a foreground Tailscale Serve session for the current desktop lifetime.

No Funnel, persistent background route, reset, or arbitrary command execution.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

import httpx
import psutil

from .phone_config import read_settings, apply_settings
from .process_lifetime import require_owned_process_tree, contain_owned_child


def owns_foreground_route(config, endpoint, origin):
    """Require a single foreground-only HTTPS handler for this exact backend."""
    if not isinstance(config, dict) or any(config.get(key) for key in ("TCP", "Web", "Services", "AllowFunnel")):
        return False
    foreground = config.get("Foreground")
    if not isinstance(foreground, dict) or len(foreground) != 1:
        return False
    row = next(iter(foreground.values()))
    if not isinstance(row, dict) or any(row.get(key) for key in ("Services", "AllowFunnel", "Foreground")):
        return False
    expected_host = urlsplit(endpoint).hostname + ":443"
    return (row.get("TCP") == {"443": {"HTTPS": True}} and
            row.get("Web") in [{expected_host: {"Handlers": {"/": {"Proxy": target}}}}
                               for target in (origin, origin + "/")])


def emit(state, message):
    print(json.dumps({"state": state, "message": message}), flush=True)


async def command(executable, *args, env=None):
    child = await asyncio.create_subprocess_exec(
        str(executable), *args, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL, env=env,
        **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}),
    )
    async def collect():
        output = bytearray()
        while chunk := await child.stdout.read(65536):
            output.extend(chunk)
            if len(output) > 1024 * 1024:
                raise ValueError("Command output exceeded the limit")
        await child.wait()
        if child.returncode:
            raise RuntimeError("Local service command failed")
        return bytes(output)
    try:
        return await asyncio.wait_for(collect(), 12)
    finally:
        if child.returncode is None:
            child.kill()
            await child.wait()


async def verify_tailscale(executable):
    env = {key: value for key, value in os.environ.items() if key.casefold() != "psmodulepath"}
    env["ORIGO_VERIFY_BINARY"] = str(executable)
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    script = ("$s=Get-AuthenticodeSignature -LiteralPath $env:ORIGO_VERIFY_BINARY; "
              "if($s.Status -ne 'Valid'){exit 1}; "
              "$s.SignerCertificate.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName,$false)")
    publisher = (await command(powershell, "-NoProfile", "-NonInteractive", "-Command", script, env=env)).decode(errors="replace").strip()
    if publisher not in {"Tailscale Inc.", "Tailscale, Inc."}:
        raise RuntimeError("A valid Tailscale-signed installation is required")


async def serve(home, port, parent_pid, backend_pid):
    settings = read_settings(home)
    if not settings or not settings["enabled"]:
        emit("off", "Phone sharing is off. Configure your private address and workstation sign-in to enable it.")
        return
    apply_settings(home, {})  # Refuse missing credentials before any sharing command.
    if port != settings["port"]:
        raise ValueError("The running backend does not match the configured pairing port")
    executable = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Tailscale/tailscale.exe"
    if os.name != "nt" or not executable.is_file():
        emit("setup_required", "Install Tailscale on this PC and your phone, sign into your private network, then restart Origo.")
        return
    require_owned_process_tree()
    await verify_tailscale(executable)
    owners = [psutil.Process(parent_pid), psutil.Process(backend_pid)]
    births = [process.create_time() for process in owners]
    # Also bind ownership to the actual dashboard child, not a PID alone.
    argv = owners[1].cmdline()
    if "hermes_cli.main" not in argv or "dashboard" not in argv or "--port" not in argv or argv[argv.index("--port") + 1] != str(port):
        raise ValueError("Dashboard ownership could not be verified")
    origin = f"http://127.0.0.1:{port}"
    endpoint = settings["endpoint"]
    async def json_command(*args):
        value = json.loads(await command(executable, *args))
        if not isinstance(value, dict):
            raise ValueError("Invalid local service response")
        return value
    status = await json_command("status", "--json")
    if status.get("BackendState") != "Running":
        emit("setup_required", "Sign into Tailscale on this PC before enabling phone sharing.")
        return
    if str(status.get("Self", {}).get("DNSName", "")).rstrip(".").lower() != urlsplit(endpoint).hostname:
        emit("setup_required", "Use this PC's exact Tailscale DNS address in Phone pairing.")
        return
    if await json_command("serve", "status", "--json"):
        emit("conflict", "Tailscale already has a sharing configuration. Origo left it unchanged; use a dedicated PC endpoint or remove that configuration yourself.")
        return
    async with httpx.AsyncClient(timeout=3, trust_env=False, follow_redirects=False) as client:
        # A reverse proxy sees this public Host. It must never receive the
        # dashboard's legacy loopback token or unauthenticated config response.
        response = await client.get(origin + "/api/config", headers={"Host": urlsplit(endpoint).netloc, "Accept": "application/json"})
        if response.status_code != 401:
            raise RuntimeError("Dashboard authentication was not confirmed; sharing refused")
    if any(not process.is_running() or process.create_time() != birth for process, birth in zip(owners, births)):
        emit("stopped", "Origo stopped before phone sharing could start.")
        return
    child = await asyncio.create_subprocess_exec(
        str(executable), "serve", "--https=443", origin,
        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        contain_owned_child(child)
    except BaseException:
        if child.returncode is None:
            child.terminate()
            await child.wait()
        raise
    async def watch_owners():
        while True:
            for process, birth in zip(owners, births):
                try:
                    if not process.is_running() or process.create_time() != birth:
                        return
                except psutil.Error:
                    return
            await asyncio.sleep(.5)
    async def watch_route():
        ready = False
        for _ in range(30):
            if child.returncode is not None:
                raise RuntimeError("Tailscale Serve stopped. Check that HTTPS is enabled for this PC")
            config = await json_command("serve", "status", "--json")
            if owns_foreground_route(config, endpoint, origin):
                ready = True
                emit("sharing", "Private phone sharing is active at " + endpoint + ". Sign in using your workstation credentials.")
                break
            if config:
                raise RuntimeError("The sharing route did not match this Origo backend")
            await asyncio.sleep(.5)
        if not ready:
            raise RuntimeError("Tailscale HTTPS setup was not completed. Enable HTTPS for this PC, then restart Origo")
        await child.wait()
    owner_task = asyncio.create_task(watch_owners())
    route_task = asyncio.create_task(watch_route())
    try:
        done, _ = await asyncio.wait([owner_task, route_task], return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in (owner_task, route_task):
            task.cancel()
        await asyncio.gather(owner_task, route_task, return_exceptions=True)
        if child.returncode is None:
            child.terminate()
            try:
                await asyncio.wait_for(child.wait(), 5)
            except asyncio.TimeoutError:
                child.kill()
                await child.wait()
        # Foreground Serve belongs to its WatchIPNBus session. Closing the CLI
        # closes that session; never reset or mutate somebody else's config.
        emit("stopped", "Phone sharing stopped with this Origo session.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--backend-pid", type=int, required=True)
    args = parser.parse_args()
    try:
        asyncio.run(serve(args.home, args.port, args.parent_pid, args.backend_pid))
    except (ValueError, RuntimeError, OSError, asyncio.TimeoutError, psutil.Error):
        emit("setup_required", "Private sharing could not start. Check Tailscale sign-in, this PC's address, HTTPS setup and backend authentication.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
