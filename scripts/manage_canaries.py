"""Explicit local canary setup; never prints the marker or overwrites vault files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from origo_runtime.canaries import CanaryRegistry
from origo_runtime.audit import AuditLog


def main():
    parser = argparse.ArgumentParser(description="Register a local vault canary for Indra's content guard")
    parser.add_argument("action", choices=["list", "create"])
    parser.add_argument("--profile-home", required=True, type=Path)
    parser.add_argument("--vault-folder", type=Path, help="Existing folder explicitly chosen for the marker file")
    parser.add_argument("--label", default="Vault canary")
    args = parser.parse_args()
    home = args.profile_home.resolve(strict=True)
    if not home.is_dir():
        parser.error("Profile home must be an existing directory")
    owner = hashlib.sha256(str(home).casefold().encode()).hexdigest()
    registry = CanaryRegistry(ROOT / "data")
    if args.action == "list":
        print(json.dumps(registry.list(owner)))
        return
    if args.vault_folder is None:
        parser.error("create requires an explicitly chosen --vault-folder")
    cfg = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8")) or {}
    if (cfg.get("security") or {}).get("untrusted_content_guard") is not True:
        parser.error("Enable security.untrusted_content_guard in this profile before creating a canary")
    registry.validate_label(args.label)
    folder = args.vault_folder.resolve(strict=True)
    if not folder.is_dir():
        parser.error("Vault folder must be an existing directory")
    target = folder / ".indra-canary.txt"
    # O_EXCL prevents overwriting a file or following a pre-existing symlink.
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            registered = registry.create(owner, args.label)
            stream.write(registered["token"] + "\n")
        AuditLog(home).append("security.canary_created", {"canary_id": registered["id"]})
    except Exception:
        # Keep a partially written marker/hash protected; do not delete vault data.
        raise RuntimeError("Canary setup did not finish. Inspect the chosen folder and local diagnostics.") from None
    print(json.dumps({"id": registered["id"], "file": str(target), "registered": True}))


if __name__ == "__main__":
    main()
