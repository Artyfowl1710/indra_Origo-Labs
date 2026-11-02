"""Validate installed skills and declarative plugin manifests without invoking plugins."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env", encoding="utf-8-sig")
from app import extensions  # noqa: E402


def main() -> int:
    skills = extensions.list_skills()
    plugins = extensions.list_plugins()
    diagnostics = extensions.plugin_diagnostics()
    report = {
        "skill_count": len(skills),
        "skills": [{"id": row["id"], "name": row["name"], "bytes": row["bytes"]} for row in skills],
        "plugin_diagnostics": diagnostics,
        "plugins": [{"id": row["id"], "name": row["name"], "enabled": row["enabled"],
                     "valid_tool_count": len(row["valid_tools"])} for row in plugins],
        "policy": "No plugin endpoint was contacted and no skill instruction was executed.",
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not skills:
        print("ERROR: no valid skills were found.", file=sys.stderr)
        return 1
    if diagnostics.get("invalid_manifest_count", 0):
        print("ERROR: one or more plugin manifests are invalid; inspect plugins/README.md.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
