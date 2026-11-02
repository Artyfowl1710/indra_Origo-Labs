#!/usr/bin/env python3
"""
Auto-configure llama-swap.yaml based on locally available GGUF models.

Scans the models/ directory, profiles known model architectures, and generates
a production-ready llama-swap.yaml file. Automatically handles multimodal
(VLM) projector mapping (--mmproj) for models like Qwen2-VL.

Usage:
    python auto-configure-models.py [--preset eco|balanced|power|ultra] [--ctx TOKENS]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# Paths relative to backend root
BACKEND_DIR = Path(__file__).resolve().parent
MODELS_DIR = BACKEND_DIR / "models"
CONFIG_OUT = BACKEND_DIR / "config" / "llama-swap.yaml"

# Platform-specific binary paths
if sys.platform == "win32":
    LLAMA_SERVER = BACKEND_DIR / "bin" / "llama-server.exe"
    LLAMA_SWAP = BACKEND_DIR / "bin" / "llama-swap.exe"
else:
    LLAMA_SERVER = BACKEND_DIR / "bin" / "llama-server"
    LLAMA_SWAP = BACKEND_DIR / "bin" / "llama-swap"

# Stop command template (PowerShell on Windows, kill on Linux/macOS)
if sys.platform == "win32":
    CMD_STOP = (
        'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe '
        '-NoProfile -Command "Stop-Process -Id ${PID} -Force -ErrorAction SilentlyContinue"'
    )
else:
    CMD_STOP = "kill -9 ${PID} 2>/dev/null || true"

# ── Context presets ───────────────────────────────────────────────────────────
CONTEXT_PRESETS: dict[str, dict] = {
    "eco": {"ctx": 8192, "batch": 128, "ubatch": 64, "label": "Eco (4-6GB VRAM, Q4_0 KV)"},
    "4k": {"ctx": 4096, "batch": 128, "ubatch": 64, "label": "Minimal (4GB VRAM)"},
    "8k": {"ctx": 8192, "batch": 128, "ubatch": 64, "label": "Eco (6-8GB VRAM)"},
    "balanced": {"ctx": 32768, "batch": 256, "ubatch": 128, "label": "Balanced (8-16GB VRAM, Q4_0 KV)"},
    "16k": {"ctx": 16384, "batch": 256, "ubatch": 128, "label": "Balanced 16K"},
    "32k": {"ctx": 32768, "batch": 256, "ubatch": 128, "label": "Power 32K (Q4_0 KV)"},
    "power": {"ctx": 49152, "batch": 512, "ubatch": 256, "label": "Power (16-24GB VRAM)"},
    "ultra": {"ctx": 65536, "batch": 512, "ubatch": 256, "label": "Ultra (24GB+ VRAM, Q4_0 KV)"},
    "64k": {"ctx": 65536, "batch": 512, "ubatch": 256, "label": "Ultra 64K"},
}

# ── Model identification patterns ────────────────────────────────────────────
VLM_PATTERNS = re.compile(r"(vl|vlm|vision|ocr|qwen2-vl)", re.IGNORECASE)
MMPROJ_PATTERN = re.compile(r"mmproj", re.IGNORECASE)

MODEL_PROFILES: dict[str, dict] = {
    "qwen3.5-4b":       {"alias": "qwen3.5-4b",              "ctx": 32768, "batch": 256, "ubatch": 128, "predict": 4096, "layers": 99, "extra": "--reasoning-budget 0 --reasoning off"},
    "qwen_qwen3.5-4b":  {"alias": "qwen3.5-4b",              "ctx": 32768, "batch": 256, "ubatch": 128, "predict": 4096, "layers": 99, "extra": "--reasoning-budget 0 --reasoning off"},
    "gemma-2-2b":        {"alias": "gemma-2-2b-it",           "ctx": 32768, "batch": 256, "ubatch": 128, "predict": 2048, "layers": 99, "extra": "--reasoning off"},
    "hermes-3-llama":    {"alias": "hermes-3-llama-8b",       "ctx": 32768, "batch": 256, "ubatch": 128, "predict": 4096, "layers": 99, "extra": "--reasoning off"},
    "qwen2-vl-ocr":      {"alias": "qwen2-vl-ocr-2b-instruct","ctx": 8192, "batch": 128, "ubatch": 64,  "predict": 1024, "layers": 99, "extra": "--reasoning off"},
    "phi-4-mini":        {"alias": "phi-4-mini-instruct",     "ctx": 16384, "batch": 256, "ubatch": 128, "predict": 2048, "layers": 99, "extra": "--reasoning off"},
}

DEFAULT_PROFILE = {"ctx": 8192, "batch": 128, "ubatch": 64, "predict": 1024, "layers": 99, "extra": "--reasoning off"}


def find_profile(filename: str) -> dict:
    """Match a GGUF filename to a known model profile."""
    name_lower = filename.lower()
    for pattern, profile in MODEL_PROFILES.items():
        if pattern.lower() in name_lower:
            return profile.copy()
    return DEFAULT_PROFILE.copy()


def derive_alias(filename: str) -> str:
    """Create a reasonable alias from a GGUF filename."""
    name = re.sub(r"[-_.]Q\d+_K.*\.gguf$", "", filename, flags=re.IGNORECASE)
    name = re.sub(r"\.gguf$", "", name, flags=re.IGNORECASE)
    name = name.replace("_", "-").replace(" ", "-").lower()
    name = re.sub(r"-+", "-", name).strip("-")
    return name


def scan_models(target_ctx: int | None = None, batch_override: int | None = None, ubatch_override: int | None = None) -> list[dict]:
    """Scan models/ directory and return model configurations."""
    if not MODELS_DIR.exists():
        print(f"[ERROR] Models directory not found: {MODELS_DIR}")
        sys.exit(1)

    gguf_files = sorted(MODELS_DIR.glob("*.gguf"))
    mmproj_files = [f for f in gguf_files if MMPROJ_PATTERN.search(f.name)]
    model_files = [f for f in gguf_files if not MMPROJ_PATTERN.search(f.name)]

    if not model_files:
        print("[WARN] No .gguf model files found in models/")
        return []

    models = []
    seen_aliases: set[str] = set()
    for model_path in model_files:
        profile = find_profile(model_path.name)
        alias = profile.get("alias") or derive_alias(model_path.name)

        if alias in seen_aliases:
            continue
        seen_aliases.add(alias)

        is_vlm = bool(VLM_PATTERNS.search(model_path.name))

        mmproj_path = None
        if is_vlm and mmproj_files:
            for mp in mmproj_files:
                mmproj_path = mp
                break

        # Apply context override if provided
        ctx = target_ctx if target_ctx else profile.get("ctx", DEFAULT_PROFILE["ctx"])
        batch = batch_override if batch_override else profile.get("batch", DEFAULT_PROFILE["batch"])
        ubatch = ubatch_override if ubatch_override else profile.get("ubatch", DEFAULT_PROFILE["ubatch"])

        entry = {
            "alias": alias,
            "path": str(model_path).replace("\\", "/"),
            "is_vlm": is_vlm,
            "mmproj": str(mmproj_path).replace("\\", "/") if mmproj_path else None,
            "ctx": ctx,
            "batch": batch,
            "ubatch": ubatch,
            "predict": profile.get("predict", DEFAULT_PROFILE["predict"]),
            "layers": profile.get("layers", DEFAULT_PROFILE["layers"]),
            "extra": profile.get("extra", DEFAULT_PROFILE["extra"]),
        }
        models.append(entry)

    return models


def generate_yaml(models: list[dict], kv_quant: str = "q4_0") -> str:
    """Generate the llama-swap.yaml content."""
    server_bin = str(LLAMA_SERVER).replace("\\", "/")

    lines = [
        "healthCheckTimeout: 180",
        "models:",
    ]

    for m in models:
        lines.append(f"  {m['alias']}:")
        lines.append(f"    cmdStop: '{CMD_STOP}'")

        if m["is_vlm"]:
            cmd_parts = [
                f'"{server_bin}"',
                "--host 127.0.0.1",
                "--port ${PORT}",
                f'--model "{m["path"]}"',
                f'--alias {m["alias"]}',
                f'--n-gpu-layers {m["layers"]} --ctx-size {m["ctx"]} --parallel 1',
                f'--batch-size {m["batch"]} --ubatch-size {m["ubatch"]} --threads 8',
                "--flash-attn on",
            ]
            if m["mmproj"]:
                cmd_parts.append(f'--mmproj "{m["mmproj"]}" --chat-template chatml --image-min-tokens 1024')
            if m["extra"]:
                cmd_parts.append(m["extra"])
            cmd_parts.append(f'--predict {m["predict"]}')
        else:
            cmd_parts = [
                f'"{server_bin}"',
                "--host 127.0.0.1",
                "--port ${PORT}",
                f'--model "{m["path"]}"',
                f'--alias {m["alias"]}',
                f'--n-gpu-layers {m["layers"]} --ctx-size {m["ctx"]} --parallel 1',
                f'--batch-size {m["batch"]} --ubatch-size {m["ubatch"]} --threads 8',
                f"--flash-attn on --cache-type-k {kv_quant} --cache-type-v {kv_quant}",
            ]
            cmd_parts.append("--jinja")
            if m["extra"]:
                cmd_parts.append(m["extra"])
            cmd_parts.append(f'--predict {m["predict"]}')

        cmd_str = " ".join(cmd_parts)
        lines.append(f"    cmd: >-")
        lines.append(f"      {cmd_str}")
        lines.append(f"    ttl: 300")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Auto-configure llama-swap.yaml with GPU context optimization")
    parser.add_argument("--preset", choices=list(CONTEXT_PRESETS.keys()), help="Context window preset (eco, balanced, power, ultra)")
    parser.add_argument("--ctx", type=int, help="Explicit context size tokens (e.g. 32768)")
    parser.add_argument("--kv-quant", choices=["q4_0", "q8_0", "f16"], default=os.environ.get("LLAMA_KV_QUANT", "q4_0"), help="KV cache quantization type (default: q4_0)")
    args = parser.parse_args()

    target_ctx = None
    batch_size = None
    ubatch_size = None

    if args.preset:
        preset_info = CONTEXT_PRESETS[args.preset]
        target_ctx = preset_info["ctx"]
        batch_size = preset_info["batch"]
        ubatch_size = preset_info["ubatch"]
        print(f"[auto-configure] Using preset: {args.preset.upper()} -> {target_ctx:,} tokens ({preset_info['label']})")
    elif args.ctx:
        target_ctx = args.ctx
        print(f"[auto-configure] Using explicit context size: {target_ctx:,} tokens")
    else:
        env_ctx = os.environ.get("WORKBENCH_CONTEXT_SIZE") or os.environ.get("INDRA_CONTEXT_SIZE")
        if env_ctx and env_ctx.isdigit():
            target_ctx = int(env_ctx)
            print(f"[auto-configure] Using context size from environment: {target_ctx:,} tokens")

    print(f"[auto-configure] Scanning: {MODELS_DIR}")
    models = scan_models(target_ctx=target_ctx, batch_override=batch_size, ubatch_override=ubatch_size)

    if not models:
        print("[auto-configure] No models found. Exiting.")
        return

    print(f"[auto-configure] Found {len(models)} model(s):")
    for m in models:
        vlm_tag = " [VLM]" if m["is_vlm"] else ""
        mmproj_tag = f" (mmproj: {Path(m['mmproj']).name})" if m["mmproj"] else ""
        print(f"  - {m['alias']}: {Path(m['path']).name} (ctx: {m['ctx']:,}){vlm_tag}{mmproj_tag}")

    print(f"[auto-configure] KV cache quantization: {args.kv_quant}")
    yaml_content = generate_yaml(models, kv_quant=args.kv_quant)

    CONFIG_OUT.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_OUT.write_text(yaml_content, encoding="utf-8")
    print(f"[auto-configure] Written: {CONFIG_OUT}")
    print("[auto-configure] Done. llama-swap will hot-reload if --watch-config is enabled.")


if __name__ == "__main__":
    main()
