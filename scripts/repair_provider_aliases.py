"""Repair known provider-domain typos in one credential store, without printing keys."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "indra/SIH-26/hermes-agent"))
ALIASES = {"opencode.ai": "opencode-zen", "openrouter.ai": "openrouter"}


def repair(home, apply=False):
    os.environ["HERMES_HOME"] = str(Path(home).resolve())
    from hermes_cli.auth import _auth_store_lock, _load_auth_store, _save_auth_store
    report = []
    with _auth_store_lock():
        store = _load_auth_store()
        pool = store.get("credential_pool", {})
        for alias, canonical in ALIASES.items():
            source = pool.get(alias)
            if not isinstance(source, list) or not source or not all(isinstance(e, dict) for e in source):
                continue
            target = pool.get(canonical, [])
            target = list(target) if isinstance(target, list) else []
            for entry in source:
                if not any((entry.get("id") and e.get("id") == entry["id"]) or
                           (entry.get("access_token") and e.get("access_token") == entry["access_token"]) for e in target if isinstance(e, dict)):
                    item = dict(entry)
                    if "provider" in item: item["provider"] = canonical
                    target.append(item)
            report.append({"from": alias, "to": canonical, "entries": len(source), "applied": apply})
            if apply:
                pool[canonical] = target
                del pool[alias]
        if report and apply:
            _save_auth_store(store)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=ROOT / "data/indra-auto-home")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(repair(args.home, args.apply)))
