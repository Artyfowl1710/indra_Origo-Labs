"""Reviewed narrative edits; technical identifiers and retained notices stay intact."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "indra/SIH-26/hermes-agent"


def edit(relative, replacements):
    path = CORE / relative
    before = path.read_text(encoding="utf-8")
    after = before
    for old, new in replacements:
        after = after.replace(old, new)
    if before != after:
        path.write_text(after, encoding="utf-8")


def main():
    edit("agent/prompt_builder.py", [
        ("Hermes appends", "Indra appends"), ("floating Hermes ", "floating Indra "),
        ("inside Hermes.", "inside Indra."), ("the Hermes terminal UI", "the Indra terminal UI"),
        ("the Hermes desktop app", "the Indra desktop app"),
        ("where Hermes itself", "where Indra itself"), ("the Hermes process", "the Indra process"),
        ("the documentation at https://hermes-agent.nousresearch.com/docs is your ", "the installed docs/INDEX.md and docs/WORKSPACE_UPGRADE.md are your "),
        ("the documentation at https://hermes-agent.nousresearch.com/docs is the ", "the installed docs/INDEX.md and docs/WORKSPACE_UPGRADE.md are the "),
        ("authoritative reference and always holds the latest, most up-to-date information.", "product reference for this build."),
        ("authoritative reference and always holds the latest, most up-to-date information.", "product reference for this build."),
    ])
    edit("web/src/pages/ChannelsPage.tsx", [("Hermes will then send", "Indra will then send")])
    edit("web/src/components/HermesConsoleModal.tsx", [('"hermes> "', '"indra> "')])
    edit("web/src/pages/ConfigPage.tsx", [('"hermes-config.json"', '"indra-config.json"')])
    edit("web/src/pages/ChatPage.tsx", [("Open this page through `hermes dashboard`, not directly.", "Launch Indra from its desktop shortcut, then open Chat.")])
    edit("hermes_cli/console_engine.py", [("Hermes Console", "Origo Console"), ('"hermes> "', '"indra> "')])
    edit("hermes_cli/web_routers/chat_ws.py", [("Hermes Console", "Origo Console"), ('"hermes> "', '"indra> "'), ("Install Hermes inside WSL2", "Install the Indra terminal runtime inside WSL2")])
    edit("hermes_cli/web_routers/mcp.py", [("Return to Hermes", "Return to Indra"), ("return to Hermes", "return to Indra")])
    edit("hermes_cli/web_routers/oauth.py", [("before Hermes ", "before Indra "), ("Managed outside Hermes", "Managed outside Indra")])
    edit("hermes_cli/web_routers/actions.py", [("Hermes updates are managed", "Indra updates are managed"), ("Hermes is managed by", "Indra is managed by")])
    edit("hermes_cli/web_routers/skills.py", [('"Hermes Index"', '"Indra Index"')])
    # Product names adjoining translated punctuation and compound nouns are
    # display copy too; paths/commands remain lowercase and are not rewritten.
    for path in (CORE / "web/src/i18n").glob("*.ts"):
        if path.name in {"index.ts", "types.ts"}:
            continue
        before = path.read_text(encoding="utf-8")
        after = re.sub(r"\bHermes\b(?![\w/])", "Indra", before)
        if after != before:
            path.write_text(after, encoding="utf-8")
    for path in (CORE / "web/src/i18n/ui-generated").glob("*.json"):
        before = json.loads(path.read_text(encoding="utf-8"))
        def text(value):
            return re.sub(r"(?<![\w./:@$-])Hermes(?![\w/.:_-])", "Indra", value)
        after = {text(k): text(v) for k, v in before.items()}
        if after != before:
            path.write_text(json.dumps(after, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    # Existing profile personas are migrated only if the whole file matches an
    # auto-seeded default. Never touch session history, keys or custom personas.
    import sys
    sys.path.insert(0, str(CORE))
    from hermes_cli.default_soul import DEFAULT_SOUL_MD, is_legacy_template_soul
    migrated = []
    for folder in (ROOT / "data").iterdir():
        if not folder.is_dir() or not folder.name.startswith("indra-"):
            continue
        path = folder / "SOUL.md"
        if path.is_file() and is_legacy_template_soul(path.read_text(encoding="utf-8")):
            path.write_text(DEFAULT_SOUL_MD, encoding="utf-8")
            migrated.append(folder.name)
    print(json.dumps({"migrated_default_personas": migrated}))


if __name__ == "__main__":
    main()
