"""Admit an approved local model into a loopback vLLM server."""

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key

MANIFEST_FORMAT = "indra-vllm-model/v1"


def _require_read_only(path: Path) -> None:
    if not os.statvfs(path).f_flag & os.ST_RDONLY:
        raise ValueError(f"Model path must be on a read-only mount: {path}")


def _inspect(path: Path, *, read_only: bool) -> int:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or (
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise ValueError(f"Model tree contains a link or reparse point: {path}")
    if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
        raise ValueError(f"Model tree contains a special file: {path}")
    if read_only:
        _require_read_only(path)
    return info.st_mode


def _manifest_bytes(value: dict) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    ).encode()


def _inventory(root: Path, *, read_only: bool) -> dict[str, str]:
    if not stat.S_ISDIR(_inspect(root, read_only=read_only)):
        raise ValueError("Model path must be a directory.")
    if read_only and root != root.resolve(strict=True):
        raise ValueError("The model mount path must be canonical and contain no symlinks.")
    files = {}
    directories = [root]
    while directories:
        for path in directories.pop().iterdir():
            if stat.S_ISDIR(_inspect(path, read_only=read_only)):
                directories.append(path)
                continue
            digest = hashlib.sha256()
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            files[path.relative_to(root).as_posix()] = digest.hexdigest()
    return files


def create_manifest(root: Path, model: str, *, read_only: bool = False) -> bytes:
    """Describe an exact file tree without downloading or loading any model code."""
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}", model):
        raise ValueError("Use a model name of up to 128 ASCII letters, digits, or ./_-.")
    files = _inventory(root, read_only=read_only)
    if "config.json" not in files or not any(name.endswith(".safetensors") for name in files):
        raise ValueError("Model tree must contain config.json and safetensors weights.")
    return _manifest_bytes({"format": MANIFEST_FORMAT, "model": model, "files": files})


def verify_model(
    root: Path, manifest: Path, signature: Path, trusted_key: Path, *, read_only: bool = False
) -> tuple[str, str]:
    """Verify the detached release signature and the full local model inventory."""
    approved = manifest.read_bytes()
    key = load_pem_public_key(trusted_key.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("The trusted release key must be Ed25519.")
    try:
        key.verify(signature.read_bytes(), approved)
    except InvalidSignature as exc:
        raise ValueError("Model manifest signature did not verify under the trusted key.") from exc
    payload = json.loads(approved)
    if not isinstance(payload, dict) or payload.get("format") != MANIFEST_FORMAT:
        raise ValueError("Unknown model manifest format.")
    model = payload.get("model")
    if create_manifest(root, model, read_only=read_only) != approved:
        raise ValueError(
            "Model files do not match the signed manifest or the manifest is noncanonical."
        )
    return model, hashlib.sha256(approved).hexdigest()


def serve(args: argparse.Namespace) -> None:
    if not sys.platform.startswith("linux"):
        raise ValueError("Verified vLLM serving requires Linux and a read-only model mount.")
    if not 1 <= args.port <= 65535 or args.max_model_len < 1:
        raise ValueError("Supply a valid port and a positive context limit.")
    if not 0 < args.gpu_memory_utilization <= 1:
        raise ValueError("GPU memory utilization must be above zero and at most one.")
    api_key = os.environ.get("VLLM_API_KEY", "")
    if not api_key.strip():
        raise ValueError("Set VLLM_API_KEY for the local inference server.")

    root = args.model_dir.absolute()
    model, digest = verify_model(
        root, args.manifest, args.signature, args.trusted_key, read_only=True
    )
    # Prevent inherited model redirects, runtime adapter updates, and loader plugins.
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("VLLM_", "HF_", "HUGGINGFACE_", "TRANSFORMERS_"))
    }
    env.update(VLLM_API_KEY=api_key, VLLM_PLUGINS="", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    command = [
        sys.executable,
        "-I",
        "-m",
        "vllm.entrypoints.cli.main",
        "serve",
        str(root),
        "--tokenizer",
        str(root),
        "--load-format",
        "safetensors",
        "--served-model-name",
        model,
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
        "--max-model-len",
        str(args.max_model_len),
        "--gpu-memory-utilization",
        str(args.gpu_memory_utilization),
        "--no-trust-remote-code",
        "--no-enable-log-requests",
    ]
    if args.enforce_eager:
        command.append("--enforce-eager")
    print(
        json.dumps({"event": "model_verified", "model": model, "manifest_sha256": digest}),
        flush=True,
    )
    os.execve(sys.executable, command, env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    manifest = commands.add_parser(
        "manifest", help="Write an unsigned manifest to stdout for release approval."
    )
    manifest.add_argument("model_dir", type=Path)
    manifest.add_argument("--model", required=True)
    verify = commands.add_parser(
        "verify", help="Verify the signature and model files without starting vLLM."
    )
    launch = commands.add_parser(
        "serve", help="Verify a read-only model tree and start a local vLLM server."
    )
    for command in (verify, launch):
        command.add_argument("model_dir", type=Path)
        command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--signature", type=Path, required=True)
        command.add_argument("--trusted-key", type=Path, required=True)
    launch.add_argument("--port", type=int, default=8100)
    launch.add_argument("--max-model-len", type=int, default=2048)
    launch.add_argument("--gpu-memory-utilization", type=float, default=0.8)
    launch.add_argument("--enforce-eager", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "manifest":
            sys.stdout.buffer.write(create_manifest(args.model_dir, args.model))
        elif args.action == "verify":
            model, digest = verify_model(
                args.model_dir, args.manifest, args.signature, args.trusted_key
            )
            print(json.dumps({"model": model, "manifest_sha256": digest}))
        else:
            serve(args)
    except (OSError, ValueError, UnsupportedAlgorithm) as exc:
        print(f"Verified vLLM: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
