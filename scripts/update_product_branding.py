"""Apply reviewed display-copy changes without renaming runtime contracts.

No dependency trees, archives, history, model files or reference folders are edited.
Run from this product checkout; the JSON report contains paths, never credentials.
"""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "indra/SIH-26/hermes-agent"
SKIP = {"node_modules", ".git", ".venv", ".indra-python", "venv", "data", "logs", "outputs", "workspace", "web_dist", "dist", "build", "__pycache__", ".pytest_cache", "tests"}
TEXT = {".py", ".ts", ".tsx", ".md", ".html", ".iss", ".yaml", ".yml", ".json", ".ps1", ".txt"}
OLD_TEAM = re.compile(r"coders?\s*by\s*chance", re.I)
DISPLAY = re.compile(r"(?<![\w./:@$-])Hermes(?![\w/.:_-])")


def main():
    changes = []
    # The previous team name is an attribution string, not an executable name.
    for directory, dirs, files in __import__("os").walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for filename in files:
            path = Path(directory) / filename
            if path.suffix not in TEXT or path.name in {"LICENSE", "NOTICE", "package-lock.json"} or path == Path(__file__).resolve():
                continue
            try:
                before = path.read_text(encoding="utf-8")
            except (UnicodeError, OSError):
                continue
            after = OLD_TEAM.sub("Origo Labs", before)
            if after != before:
                path.write_text(after, encoding="utf-8")
                changes.append({"path": str(path.relative_to(ROOT)), "change": "team attribution"})
    # These catalogs contain display values. Property keys, lowercase commands,
    # dot paths, URLs, storage keys and package names stay byte-for-byte intact.
    for path in (CORE / "web/src/i18n").glob("*.ts"):
        if path.name in {"index.ts", "types.ts"}:
            continue
        before = path.read_text(encoding="utf-8")
        after = DISPLAY.sub("Indra", before)
        if after != before:
            path.write_text(after, encoding="utf-8")
            changes.append({"path": str(path.relative_to(ROOT)), "change": "localized product copy"})
    output = ROOT / "data/test-results/branding-changes.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(changes, indent=2), encoding="utf-8")
    print(json.dumps({"changed_files": len(changes), "report": str(output)}))


if __name__ == "__main__":
    main()
