"""Conservative, read-only Git inspection using fixed argv and a sanitized environment."""
from __future__ import annotations
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

MAX_OUTPUT_CHARS = 14000


def git_status() -> dict[str, Any]:
    from .tools import ensure_workspace, redact_sensitive_text
    root = ensure_workspace().resolve()
    git_marker = root / ".git"
    if not git_marker.exists():
        return {"available": True, "is_repository": False, "workspace": ".", "summary": "This workspace is not a Git repository.", "entries": []}
    if git_marker.is_symlink():
        return {"available": False, "is_repository": False, "error": "The workspace .git marker is a symlink; Git inspection is blocked."}
    binary = shutil.which("git")
    if not binary:
        return {"available": False, "is_repository": True, "error": "Git was not found on PATH. Install Git for Windows or add it to PATH."}
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat", "GIT_OPTIONAL_LOCKS": "0"})
    args = [binary, "--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
            "-c", "color.ui=false", "status", "--short", "--branch", "--untracked-files=no"]
    try:
        proc = subprocess.run(args, cwd=str(root), env=env, shell=False, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=5, check=False)
    except subprocess.TimeoutExpired:
        return {"available": True, "is_repository": True, "error": "Git status exceeded its 5-second read-only inspection budget."}
    except OSError as exc:
        return {"available": False, "is_repository": True, "error": f"Git status could not start ({type(exc).__name__})."}
    raw = (proc.stdout or "")[:MAX_OUTPUT_CHARS]
    if proc.returncode != 0:
        # Avoid reflecting Git configuration or file contents into UI errors.
        return {"available": True, "is_repository": True, "error": "Git status failed. Check whether this folder is a valid repository and inspect the local server log."}
    lines = [redact_sensitive_text(line)[:500] for line in raw.splitlines()[:250]]
    branch = lines[0][3:] if lines and lines[0].startswith("## ") else "unknown"
    entries = [line for line in lines if not line.startswith("## ")]
    modified = sum(1 for line in entries if line[:2].strip() in {"M", "MM", "AM", "MD", " D", "D"} or "M" in line[:2])
    added = sum(1 for line in entries if "A" in line[:2] or line.startswith("??"))
    deleted = sum(1 for line in entries if "D" in line[:2])
    return {"available": True, "is_repository": True, "branch": branch, "entries": entries,
            "modified": modified, "added": added, "deleted": deleted,
            "truncated": len(proc.stdout or "") > MAX_OUTPUT_CHARS or len((proc.stdout or "").splitlines()) > 250,
            "summary": f"{branch} · {len(entries)} changed tracked/untracked entries shown (status only; no files changed).",
            "scope": "Read-only git status; no hooks, commits, checkout, reset or fetch operations are requested."}
