"""Create a Markdown-only skill skeleton; it never creates executable code."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Human-readable skill name")
    parser.add_argument("--description", default="A reviewed Markdown workflow skill")
    args = parser.parse_args()
    slug = re.sub(r"[^a-z0-9_-]+", "-", args.name.casefold()).strip("-_")[:60]
    if not slug or not re.fullmatch(r"[a-z0-9_-]{1,60}", slug):
        parser.error("name must contain at least one ASCII letter or digit")
    target_dir = SKILLS / slug
    target = target_dir / "SKILL.md"
    if target.exists():
        parser.error(f"skill already exists: {target.relative_to(ROOT)}")
    description = " ".join(args.description.split())[:220]
    if not description or any(ch in description for ch in "\r\n"):
        parser.error("description must be a non-empty single line")
    target_dir.mkdir(parents=True, exist_ok=False)
    target.write_text(f"---\nname: {args.name[:80]}\ndescription: {description}\n---\n# {args.name[:80]}\n\n## Workflow\n\n1. Define the desired outcome and evidence required.\n2. Inspect relevant user-provided context and primary sources.\n3. Work in small, verifiable steps; respect harness policy and approvals.\n4. Report findings, uncertainties, and tests actually run.\n", encoding="utf-8", newline="\n")
    print(f"Created {target.relative_to(ROOT)}")
    print("Review the Markdown, then use Extensions → Refresh registry. No code is executed by a skill.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
