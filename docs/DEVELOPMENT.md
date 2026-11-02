# Developer guide

## Source layout

```text
app/                 FastAPI app, agent harness, tools, RAG, state store
app/static/          HTML, CSS and browser JavaScript
android/OrigoRemote/ Android Studio companion project (source only)
docker/              Docker sandbox image definition
scripts/             doctor, smoke, harness evaluation, extension validation
skills/              Markdown workflow skills
plugins/              Declarative plugin manifests and examples
tests/               unittest regression suite
docs/                User, architecture, security and release documentation
```

## Environment

Use Python 3.10+ and a project-local virtual environment. Keep `.env`, `data`, `workspace`, logs and build credentials out of source control. The supported Windows launcher creates the environment and runs a set of offline checks.

## Change principles

- Make tools narrow, explicit, bounded and auditable.
- Treat model output, web pages, retrieved documents, plugin responses and user-supplied files as untrusted.
- Add a regression test for every security or state bug.
- Keep sensitive side effects behind permission decisions.
- Do not add host-shell fallback to the Docker runner.
- Do not let a retrieved document grant permissions or override system policy.
- Keep remote access opt-in and preserve loopback binding.
- Keep feature claims aligned with actual tests and runtime evidence.

## Add a skill

Create a directory under `skills/<skill-id>/SKILL.md`. Follow the skill format used by neighboring files, keep instructions specific and safe, and validate:

```powershell
.\.venv\Scripts\python.exe scripts\validate_extensions.py
```

Skills are Markdown context, not Python plugins. Do not include secrets or instruct a skill to bypass approval controls.

## Add a plugin

Read `plugins/README.md` and `docs/EXTENSIONS_AND_WEB.md`. Plugin manifests are declarative; the host does not import third-party code into the main process. Keep plugins disabled by default and use a loopback service that you control. A manifest's `read_only` flag is an assertion, not a security guarantee.

## Frontend work

Update `app/static/index.html`, `style.css`, and `app.js` together. Keep state transitions explicit, guard async responses against stale request epochs, announce meaningful status changes, support keyboard use, and test narrow/mobile widths. Run `node --check app/static/app.js` when Node is available.

## RAG changes

Add tests for ingestion type/size bounds, secret scrubbing, retrieval ranking, source metadata, stale evidence, optional embedding failures and deletion behavior. Do not add automatic external embedding without a clear privacy opt-in. Keep PDF parsing disabled until the advisory gate is cleared.

## Security-sensitive changes

For changes to remote auth, host validation, network fetching, filesystem paths, permissions, subprocesses or data exports, update `SECURITY_MODEL.md` and the audit. Include positive and negative tests. Never claim “secure” based only on a passing unit suite.
