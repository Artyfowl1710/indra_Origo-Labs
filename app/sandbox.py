"""Opt-in Docker execution sandbox for untrusted project commands.

Commands are argv arrays (no host shell). Only a sanitized snapshot is copied into a
container-local, size-bounded tmpfs; the original workspace is never bind-mounted. The
container has no network, read-only root FS, dropped Linux capabilities, a non-root command
user, memory/CPU/PID/time limits and no automatic write-back. Docker Desktop and its image
remain trusted parts of the computing base.
"""
from __future__ import annotations
import difflib
import io
import os
import shutil
import subprocess
import tempfile
import tarfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

MAX_STAGE_FILES = 5000
MAX_STAGE_BYTES = 100 * 1024 * 1024
MAX_COMMAND_ARGS = 24
MAX_ARGUMENT_CHARS = 1000
MAX_OUTPUT_CHARS = 12000
_status_lock = threading.Lock()
_status_cache: tuple[float, dict[str, Any]] | None = None
_runtime_enabled: bool | None = None
_image_override: str | None = None
_result_lock = threading.RLock()
_completed_result_files: dict[str, dict[str, Any]] = {}
_RESULT_TTL_SECONDS = 900
_RESULT_MAX_RUNS = 8
_RESULT_MAX_CONTENT_BYTES = 1_000_000
_RESULT_MAX_FILE_BYTES = 200_000


def _prune_result_cache() -> None:
    now = time.time()
    expired = [key for key, row in _completed_result_files.items()
               if now - float(row.get("created_at", 0)) > _RESULT_TTL_SECONDS]
    for key in expired:
        _completed_result_files.pop(key, None)
    if len(_completed_result_files) > _RESULT_MAX_RUNS:
        oldest = sorted(_completed_result_files.items(), key=lambda item: float(item[1].get("created_at", 0)))
        for key, _ in oldest[:len(_completed_result_files) - _RESULT_MAX_RUNS]:
            _completed_result_files.pop(key, None)


def _remember_result_files(run_id: str, workspace: Path, files: dict[str, str]) -> None:
    """Hold sanitized, text-only changed files briefly so the user can convert them to proposals."""
    bounded: dict[str, str] = {}
    total = 0
    for rel, content in files.items():
        size = len(content.encode("utf-8"))
        if size > _RESULT_MAX_FILE_BYTES or total + size > _RESULT_MAX_CONTENT_BYTES:
            continue
        bounded[rel] = content
        total += size
    with _result_lock:
        _prune_result_cache()
        _completed_result_files[run_id] = {"created_at": time.time(), "workspace": str(workspace.resolve()),
                                           "files": bounded, "bytes": total}
        _prune_result_cache()


def get_cached_result_files(run_id: str, workspace: Path) -> dict[str, str] | None:
    """Return available sanitized text results for the workspace that created the run."""
    with _result_lock:
        _prune_result_cache()
        row = _completed_result_files.get(run_id)
        if not row or row.get("workspace") != str(workspace.resolve()):
            return None
        return dict(row.get("files", {}))


def claim_cached_result_files(run_id: str, workspace: Path, paths: list[str]) -> dict[str, str] | None:
    """One-time claim to prevent repeated clicks creating duplicate proposals for the same result."""
    with _result_lock:
        _prune_result_cache()
        row = _completed_result_files.get(run_id)
        if not row or row.get("workspace") != str(workspace.resolve()):
            return None
        files = row.get("files", {})
        if not paths or len(set(paths)) != len(paths) or any(path not in files for path in paths):
            return None
        claimed = {path: files[path] for path in paths}
        for path in paths:
            files.pop(path, None)
        return claimed


def network_mode_argument(network_access: bool) -> str:
    if not isinstance(network_access, bool):
        raise ValueError("network_access must be a boolean")
    # Docker bridge mode grants broad outbound reachability; it is not domain filtering.
    return "--network=bridge" if network_access else "--network=none"


def set_runtime_enabled(value: bool | None) -> None:
    """Override the environment toggle for this local UI session; None restores .env behavior."""
    global _runtime_enabled, _status_cache
    _runtime_enabled = value
    _status_cache = None


def set_image_override(value: str | None) -> None:
    """Select a locally configured image; None returns to the .env image."""
    global _image_override, _status_cache
    if value is not None:
        if (not isinstance(value, str) or not value.strip() or len(value) > 160
                or any(ch.isspace() or ord(ch) < 32 for ch in value)
                or value.startswith("-") or "," in value):
            raise ValueError("Sandbox image reference is invalid.")
        value = value.strip()
    _image_override = value
    _status_cache = None


def _configured_image() -> str:
    return (_image_override or os.getenv("INDRA_SANDBOX_IMAGE", "python:3.12-slim")).strip()


def is_enabled() -> bool:
    if _runtime_enabled is not None:
        return _runtime_enabled
    return os.getenv("INDRA_ENABLE_DOCKER_SANDBOX", "false").strip().lower() in {"1", "true", "yes", "on"}


def _bounded_int_env(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.getenv(name, str(default)).strip())
    except (ValueError, TypeError, AttributeError):
        value = default
    return max(low, min(value, high))


def _resource_limits() -> dict[str, Any]:
    """Configurable sandbox resource limits with hard safety ceilings."""
    try:
        cpus = float(os.getenv("INDRA_SANDBOX_CPUS", "2").strip())
    except (ValueError, TypeError, AttributeError):
        cpus = 2.0
    if not (0.5 <= cpus <= 4.0):
        cpus = max(0.5, min(cpus if cpus == cpus and abs(cpus) != float("inf") else 2.0, 4.0))
    memory_mb = _bounded_int_env("INDRA_SANDBOX_MEMORY_MB", 1024, 512, 4096)
    pids = _bounded_int_env("INDRA_SANDBOX_PIDS", 256, 64, 512)
    workspace_mb = _bounded_int_env("INDRA_SANDBOX_WORKSPACE_TMPFS_MB", 256, 128, 512)
    return {"memory_mb": memory_mb, "cpus": cpus, "pids": pids, "workspace_tmpfs_mb": workspace_mb,
            "workspace_tmpfs_bytes": workspace_mb * 1024 * 1024}


def docker_binary() -> str | None:
    configured = os.getenv("INDRA_DOCKER_BINARY", "").strip()
    return configured if configured and Path(configured).is_file() else (shutil.which("docker") if not configured else None)


def _probe_status() -> dict[str, Any]:
    binary = docker_binary()
    enabled = is_enabled()
    image = _configured_image()
    daemon = False
    image_available = False
    version = None
    detail = "Disabled by default. Set INDRA_ENABLE_DOCKER_SANDBOX=true after installing Docker Desktop."
    if enabled and not binary:
        detail = "Docker CLI was not found. Install Docker Desktop; the harness never falls back to host command execution."
    elif enabled and binary:
        try:
            probe = subprocess.run([binary, "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True, timeout=2.5, check=False)
            daemon = probe.returncode == 0
            version = probe.stdout.strip()[:80] if daemon else None
        except (OSError, subprocess.TimeoutExpired):
            daemon = False
        if daemon:
            try:
                image_probe = subprocess.run([binary, "image", "inspect", image], capture_output=True, text=True, timeout=3, check=False)
                image_available = image_probe.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                image_available = False
            detail = "Ready. Commands run in a disposable, sanitized snapshot." if image_available else f"Docker is running, but image '{image}' is not available locally. Pull it manually; Indra will not download images implicitly."
        else:
            detail = "Docker CLI exists but the daemon is not responding. Start Docker Desktop and retry Diagnostics."
    limits = _resource_limits()
    return {"enabled": enabled, "docker_available": bool(binary), "daemon_available": daemon,
            "image_available": image_available, "docker_version": version, "image": image or "(invalid image)",
            "network": "none by default; bridge only for an explicitly approved run and not domain-filtered",
            "workspace_mode": f"sanitized ephemeral snapshot in container-local {limits['workspace_tmpfs_mb']} MiB tmpfs; original workspace is not bind-mounted; no automatic write-back",
            "limits": {"memory": f"{limits['memory_mb']}m", "cpus": limits["cpus"], "pids": limits["pids"], "timeout_seconds": 45,
                       "max_files": MAX_STAGE_FILES, "max_snapshot_bytes": MAX_STAGE_BYTES,
                       "max_sandbox_workspace_bytes": limits["workspace_tmpfs_bytes"]},
            "ready": bool(enabled and binary and daemon and image_available), "detail": detail}


def status() -> dict[str, Any]:
    global _status_cache
    if not is_enabled():
        return _probe_status()
    now = time.monotonic()
    with _status_lock:
        if _status_cache and now - _status_cache[0] < 5:
            return dict(_status_cache[1])
        value = _probe_status()
        _status_cache = (now, value)
        return dict(value)


def _safe_copy_workspace(source: Path, target: Path) -> tuple[dict[str, bytes], int, int]:
    """Copy only safe, readable text files into an isolated staging tree.

    Binary weights, databases, caches and arbitrary non-text artifacts are excluded. Common
    inline credentials are best-effort redacted before entering the sandbox copy.
    """
    from .tools import SKIP_DIRS, SENSITIVE_DIRS, _is_link_like, is_readable_text_file, is_sensitive_path, redact_sensitive_text
    source = source.resolve(strict=True)
    before: dict[str, bytes] = {}
    total_bytes = total_files = visited_dirs = 0
    for current, dirs, files in os.walk(source, topdown=True, followlinks=False):
        visited_dirs += 1
        if visited_dirs > 10000:
            break
        base = Path(current)
        dirs[:] = [d for d in dirs if d.casefold() not in SKIP_DIRS and d.casefold() not in SENSITIVE_DIRS and not _is_link_like(base / d)][:2000]
        for name in sorted(files):
            path = base / name
            if _is_link_like(path) or is_sensitive_path(path) or not is_readable_text_file(path):
                continue
            try:
                if not path.is_file():
                    continue
                rel = path.relative_to(source)
                if any(part in {".", ".."} or ":" in part or any(ord(ch) < 32 for ch in part) for part in rel.parts):
                    continue
                size = path.stat().st_size
                if size > 8_000_000 or total_files >= MAX_STAGE_FILES or total_bytes + size > MAX_STAGE_BYTES:
                    continue
                raw = path.read_bytes()
                decoded = raw.decode("utf-8")
                data = redact_sensitive_text(decoded).encode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if total_bytes + len(data) > MAX_STAGE_BYTES:
                continue
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            before[rel.as_posix()] = data
            total_files += 1; total_bytes += len(data)
    return before, total_files, total_bytes


def _run_small(args: list[str], timeout: float = 10.0) -> subprocess.CompletedProcess:
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)


def _stage_snapshot(binary: str, container: str, files: dict[str, bytes]) -> subprocess.CompletedProcess:
    """Stream regular sanitized files into tmpfs, without daemon-side docker cp.

    Docker Engine 29 rejects cp into a read-only container root even when the
    destination is writable tmpfs. Extraction runs inside that same restricted
    container; the root filesystem stays read-only and no host mount is added.
    """
    with tempfile.TemporaryFile() as archive:
        with tarfile.open(fileobj=archive, mode="w") as bundle:
            for name, data in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o644
                bundle.addfile(info, io.BytesIO(data))
        archive.seek(0)
        return subprocess.run([binary, "exec", "-i", "--user", "0", container,
                               "tar", "-xf", "-", "-C", "/workspace"],
                              stdin=archive, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=20, check=False)


def _collect_snapshot(binary: str, container: str, target: Path) -> subprocess.CompletedProcess:
    """Read the live tmpfs through exec; never extract untrusted tar paths."""
    args = [binary, "exec", "--user", "0", container, "tar", "-cf", "-", "-C", "/workspace", "."]
    with tempfile.TemporaryFile() as archive:
        proc = subprocess.run(args, stdout=archive, stderr=subprocess.PIPE, timeout=20, check=False)
        if proc.returncode:
            return proc
        if archive.tell() > MAX_STAGE_BYTES + MAX_STAGE_FILES * 2048:
            return subprocess.CompletedProcess(args, 1, b"", b"Result snapshot exceeds collection limit.")
        archive.seek(0)
        total = count = 0
        try:
            with tarfile.open(fileobj=archive, mode="r:") as bundle:
                for member in bundle:
                    if member.isdir():
                        continue
                    from pathlib import PurePosixPath
                    name = PurePosixPath(member.name)
                    if (not member.isfile() or member.issparse() or name.is_absolute()
                            or ".." in name.parts or any("\\" in part or ":" in part for part in name.parts)):
                        return subprocess.CompletedProcess(args, 1, b"", b"Unsafe result snapshot entry rejected.")
                    count += 1
                    total += member.size
                    if count > MAX_STAGE_FILES or total > MAX_STAGE_BYTES:
                        return subprocess.CompletedProcess(args, 1, b"", b"Result snapshot exceeds collection limit.")
                    destination = target.joinpath(*name.parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.extractfile(member) as source, destination.open("wb") as output:
                        shutil.copyfileobj(source, output)
        except (tarfile.TarError, OSError, ValueError):
            return subprocess.CompletedProcess(args, 1, b"", b"Invalid result snapshot rejected.")
        return subprocess.CompletedProcess(args, 0, b"", b"")


def _stream_capped(pipe, result: list[bytes], limit: int):
    remaining = limit
    while True:
        chunk = pipe.read(4096)
        if not chunk:
            break
        if remaining > 0:
            keep = chunk[:remaining]
            result.append(keep)
            remaining -= len(keep)




def pull_image_after_explicit_confirmation(confirmed: bool, timeout_seconds: int = 300) -> dict[str, Any]:
    """Pull the configured sandbox image only after a deliberate UI confirmation."""
    if confirmed is not True:
        return {"error": "Explicit confirmation is required before contacting the container registry."}
    binary = docker_binary()
    if not binary:
        return {"error": "Docker CLI was not found. Install Docker Desktop first."}
    image = _configured_image()
    if not image or len(image) > 160 or any(ch.isspace() for ch in image) or image.startswith("-") or "," in image:
        return {"error": "INDRA_SANDBOX_IMAGE is invalid."}
    try:
        daemon = _run_small([binary, "info", "--format", "{{.ServerVersion}}"], timeout=4)
        if daemon.returncode != 0:
            return {"error": "Docker daemon is unavailable. Start Docker Desktop and retry."}
        result = _run_small([binary, "pull", image], timeout=max(30, min(int(timeout_seconds), 300)))
    except subprocess.TimeoutExpired:
        return {"error": "Image pull timed out. Check Docker Desktop; the container may still be cached partially."}
    except OSError as exc:
        return {"error": f"Could not start Docker image pull ({type(exc).__name__})."}
    output = ((result.stdout or b"") + b"\n" + (result.stderr or b"")).decode("utf-8", errors="replace")[-5000:]
    if result.returncode != 0:
        return {"error": "Docker image pull failed. Check registry access and Docker logs.", "output": output}
    global _status_cache
    _status_cache = None
    return {"status": "pulled", "image": image, "output": output, "network": "used only for this explicit image pull"}

def build_dev_image_after_explicit_confirmation(confirmed: bool, timeout_seconds: int = 600) -> dict[str, Any]:
    """Build the reviewed dev image from only docker/; this operation itself needs internet.

    The explicit local UI confirmation is separate from the command sandbox policy because the
    build is a host-side Docker-daemon operation that downloads a base image and packages.
    """
    if confirmed is not True:
        return {"error": "Explicit confirmation is required before building a Docker image or downloading packages."}
    binary = docker_binary()
    if not binary:
        return {"error": "Docker CLI was not found. Install Docker Desktop first."}
    project_root = Path(__file__).resolve().parent.parent
    context_dir = (project_root / "docker").resolve()
    dockerfile = context_dir / "Dockerfile.dev-sandbox"
    if not context_dir.is_dir() or not dockerfile.is_file():
        return {"error": "The reviewed Docker sandbox build context is missing."}
    try:
        daemon = _run_small([binary, "info", "--format", "{{.ServerVersion}}"], timeout=4)
        if daemon.returncode != 0:
            return {"error": "Docker daemon is unavailable. Start Docker Desktop and retry."}
        build_timeout = max(60, min(int(timeout_seconds), 600))
        command = [binary, "build", "--pull", "--file", str(dockerfile), "--tag", "indra-sandbox:dev", "."]
        env = os.environ.copy()
        env["BUILDKIT_PROGRESS"] = "plain"
        completed = subprocess.run(command, cwd=str(context_dir), env=env, capture_output=True, timeout=build_timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        output = b"\n".join(x for x in (exc.stdout, exc.stderr) if isinstance(x, bytes)).decode("utf-8", errors="replace")[-4000:]
        return {"error": "Docker image build timed out. Partial layer cache may remain; check Docker Desktop before retrying.", "output": output}
    except (OSError, ValueError, TypeError) as exc:
        return {"error": f"Could not run the Docker image build ({type(exc).__name__})."}
    output = ((completed.stdout or b"") + b"\n" + (completed.stderr or b"")).decode("utf-8", errors="replace")[-6000:]
    if completed.returncode != 0:
        return {"error": "Docker development image build failed. Review Docker Desktop output and retry after fixing the first failing step.", "output": output}
    global _status_cache
    _status_cache = None
    return {"status": "built", "image": "indra-sandbox:dev", "output": output,
            "context": "docker/ only", "host_workspace_in_build_context": False,
            "network": "used to pull the base image and packages only after explicit confirmation"}


def run_sandboxed(command: list[str], cwd: str = ".", timeout_seconds: int = 30, network_access: bool = False) -> dict[str, Any]:
    if not is_enabled():
        return {"error": "Docker sandbox execution is disabled. Set INDRA_ENABLE_DOCKER_SANDBOX=true after installing Docker Desktop."}
    binary = docker_binary()
    if not binary:
        return {"error": "Docker CLI was not found. Install and start Docker Desktop; the harness will not fall back to host-shell execution."}
    if not isinstance(command, list) or not command or len(command) > MAX_COMMAND_ARGS:
        return {"error": f"command must be an argv array with 1–{MAX_COMMAND_ARGS} arguments; shell strings are not accepted."}
    if any(not isinstance(part, str) or not part or len(part) > MAX_ARGUMENT_CHARS or "\x00" in part for part in command):
        return {"error": "Each command argument must be a non-empty string of at most 1,000 characters."}
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool) or not 1 <= timeout_seconds <= 45:
        return {"error": "timeout_seconds must be an integer from 1 to 45."}
    if not isinstance(network_access, bool):
        return {"error": "network_access must be a boolean. Network is disabled unless explicitly approved."}
    try:
        from . import tools as tool_module
        workspace_root = tool_module.WORKSPACE.resolve(strict=True)
        target_cwd = tool_module.safe_path(cwd)
        relative_cwd = target_cwd.resolve().relative_to(workspace_root).as_posix()
    except (ValueError, OSError) as exc:
        return {"error": f"Sandbox working directory was rejected ({type(exc).__name__})."}
    if not target_cwd.is_dir():
        return {"error": "Sandbox working directory is not a directory inside the selected workspace."}
    image = _configured_image()
    if not image or len(image) > 160 or any(ch.isspace() for ch in image) or image.startswith("-") or "," in image:
        return {"error": "INDRA_SANDBOX_IMAGE is invalid. Use a local Linux image tag without spaces or commas."}
    current_status = status()
    if not current_status.get("ready"):
        return {"error": current_status.get("detail") or "Docker sandbox is not ready."}
    run_id = uuid.uuid4().hex[:12]
    container_name = "indra-sandbox-" + run_id
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="indra-sandbox-") as tempdir:
        stage_in = Path(tempdir) / "input"
        stage_out = Path(tempdir) / "output"
        stage_in.mkdir(); stage_out.mkdir()
        try:
            original, file_count, byte_count = _safe_copy_workspace(workspace_root, stage_in)
        except (OSError, ValueError) as exc:
            return {"error": f"Could not stage workspace safely ({type(exc).__name__})."}

        # Container-local tmpfs is size-capped; the host workspace is never mounted into Docker.
        network_arg = network_mode_argument(network_access)
        resources = _resource_limits()
        tmp_mb = resources["workspace_tmpfs_mb"]
        create = [binary, "create", "--name", container_name, network_arg,
                  f"--memory={resources['memory_mb']}m", f"--memory-swap={resources['memory_mb']}m",
                  f"--cpus={resources['cpus']:g}", f"--pids-limit={resources['pids']}", "--read-only", "--security-opt=no-new-privileges", "--cap-drop=ALL",
                  "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m",
                  "--tmpfs", f"/workspace:rw,nosuid,nodev,noexec,size={tmp_mb}m",
                  "--env", "HOME=/tmp", "--env", "PYTHONDONTWRITEBYTECODE=1", image,
                  "/bin/sh", "-c", "while :; do sleep 3600; done"]
        created = False
        try:
            proc = _run_small(create, timeout=8)
            if proc.returncode != 0:
                body = (proc.stderr or proc.stdout).decode("utf-8", errors="replace")[:2000]
                return {"error": "Docker could not create the isolated container. Confirm the configured Linux image has /bin/sh and sleep, and review Docker status. " + body}
            created = True
            start = _run_small([binary, "start", container_name], timeout=8)
            if start.returncode != 0:
                return {"error": "Docker could not start the isolated container."}
            copy_in = _stage_snapshot(binary, container_name, original)
            if copy_in.returncode != 0:
                detail = copy_in.stderr.decode("utf-8", errors="replace")[:1000]
                return {"error": "Could not stage the sanitized workspace into the container. " + detail}
            # Files copied by Docker may be root-owned; chmod works on files the container creator owns,
            # while the actual user workload runs as a non-root UID with no Linux capabilities.
            chmod = _run_small([binary, "exec", "--user", "0", container_name, "chmod", "-R", "a+rwX", "/workspace"], timeout=8)
            if chmod.returncode != 0:
                return {"error": "Could not prepare the disposable workspace permissions; command was not run."}
            workdir = "/workspace" if relative_cwd == "." else "/workspace/" + relative_cwd
            args = [binary, "exec", "--user", "65534:65534", "--workdir", workdir, container_name, *command]
            try:
                user_proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
            except OSError as exc:
                return {"error": f"Could not start the Docker exec command ({type(exc).__name__})."}
            out_parts: list[bytes] = []; err_parts: list[bytes] = []
            out_thread = threading.Thread(target=_stream_capped, args=(user_proc.stdout, out_parts, MAX_OUTPUT_CHARS), daemon=True)
            err_thread = threading.Thread(target=_stream_capped, args=(user_proc.stderr, err_parts, MAX_OUTPUT_CHARS), daemon=True)
            out_thread.start(); err_thread.start()
            try:
                return_code = user_proc.wait(timeout=timeout_seconds)
                timed_out = False
            except subprocess.TimeoutExpired:
                user_proc.kill()
                try: user_proc.wait(timeout=3)
                except subprocess.TimeoutExpired: pass
                return_code = None; timed_out = True
            out_thread.join(timeout=2); err_thread.join(timeout=2)
            stdout = b"".join(out_parts).decode("utf-8", errors="replace")
            stderr = b"".join(err_parts).decode("utf-8", errors="replace")
            # Capture changed files only after the execution limit is enforced. Container tmpfs is capped by validated settings.
            copy_out = _collect_snapshot(binary, container_name, stage_out)
            if copy_out.returncode != 0:
                return {"error": "Command ran in the sandbox but the result snapshot could not be collected; no host files were changed."}
            changed = []; changed_count = 0; after_paths = set(); after_bytes = 0; after_scan_truncated = False
            proposal_contents: dict[str, str] = {}; proposal_bytes = 0
            for current, dirs, files in os.walk(stage_out, topdown=True, followlinks=False):
                base = Path(current)
                dirs[:] = [d for d in dirs if not (base / d).is_symlink()][:2000]
                for name in files:
                    if len(after_paths) >= MAX_STAGE_FILES:
                        after_scan_truncated = True
                        break
                    path = base / name
                    if path.is_symlink():
                        continue
                    rel = path.relative_to(stage_out).as_posix()
                    after_paths.add(rel)
                    try:
                        if path.stat().st_size > resources["workspace_tmpfs_bytes"] - after_bytes:
                            continue
                        data = path.read_bytes(); after_bytes += len(data)
                    except OSError:
                        continue
                    if rel not in original or original[rel] != data:
                        changed_count += 1
                        if len(changed) < 20:
                            before = original.get(rel, b"").decode("utf-8", errors="replace").splitlines(keepends=True)
                            after = data.decode("utf-8", errors="replace").splitlines(keepends=True)
                            diff = "".join(difflib.unified_diff(before, after, fromfile="before/" + rel, tofile="sandbox/" + rel, n=2))
                            proposable = False
                            try:
                                from . import tools as tool_module
                                candidate = tool_module.safe_path(rel)
                                decoded = data.decode("utf-8")
                                clean = tool_module.redact_sensitive_text(decoded)
                                eligible = (tool_module.is_readable_text_file(candidate)
                                            and not tool_module.is_sensitive_path(candidate)
                                            and not candidate.is_dir()
                                            and "\x00" not in decoded
                                            and len(clean.encode("utf-8")) <= min(tool_module.MAX_FILE_BYTES, _RESULT_MAX_FILE_BYTES))
                                if eligible and proposal_bytes + len(clean.encode("utf-8")) <= _RESULT_MAX_CONTENT_BYTES:
                                    proposal_contents[rel] = clean
                                    proposal_bytes += len(clean.encode("utf-8"))
                                    proposable = True
                            except (OSError, ValueError, UnicodeDecodeError):
                                proposable = False
                            changed.append({"path": rel, "bytes": len(data), "diff": diff[:3000], "proposable": proposable})
                if after_scan_truncated:
                    break
            removed = sorted(set(original) - after_paths)[:50]
            if proposal_contents:
                _remember_result_files(run_id, workspace_root, proposal_contents)
            elapsed = round((time.perf_counter() - started) * 1000, 2)
            return {"sandbox_run_id": run_id, "return_code": return_code, "timed_out": timed_out,
                    "duration_ms": elapsed, "staged_files": file_count, "staged_bytes": byte_count,
                    "stdout": stdout, "stderr": stderr, "output_truncated": len(stdout) >= MAX_OUTPUT_CHARS or len(stderr) >= MAX_OUTPUT_CHARS,
                    "changed_files_count": changed_count, "changed_files": changed, "removed_files": removed,
                    "proposable_files": sorted(proposal_contents),
                    "changed_file_scan_truncated": after_scan_truncated,
                    "writeback": False, "network": "bridge (explicitly approved for this run)" if network_access else "disabled",
                    "network_access": network_access, "image": image,
                    "note": ("Command ran in a disposable Docker container with outbound bridge networking explicitly approved for this run. Network destinations are not domain-restricted; the host workspace was not bind-mounted." if network_access else "Command ran in a disposable Docker container with no network and a size-bounded workspace tmpfs. Changes shown here were NOT applied to the real workspace.")}
        except subprocess.TimeoutExpired:
            return {"error": "Docker sandbox setup or snapshot transfer timed out; no host workspace files were changed."}
        finally:
            if created:
                try: _run_small([binary, "rm", "-f", container_name], timeout=8)
                except (OSError, subprocess.TimeoutExpired): pass
