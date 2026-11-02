# Testing, release and repository hygiene

## Local validation (Windows PowerShell)

Run from the repository root after setup:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q app tests scripts
node --check app\static\app.js # optional if Node.js installed
.\.venv\Scripts\python.exe scripts\validate_extensions.py
```

For pytest users (only if installed):

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Do not assume a test result from one environment proves another environment's dependencies or OS behavior. The release-specific counts and environment limitations are recorded in `STATUS.md` and `SECURITY_AUDIT_1.7.2.md`.

## Manual smoke test

- [ ] Start and stop from the supported launcher.
- [ ] Confirm local health endpoint and UI.
- [ ] Confirm diagnostics distinguishes app health from model availability.
- [ ] Run a simple chat against a reachable model.
- [ ] Cancel a long response and confirm UI state recovers.
- [ ] Create/rename/delete a test session.
- [ ] Inspect a file, propose an edit, deny it, then approve a separate disposable edit and verify backup/undo behavior.
- [ ] Confirm agent web access asks before network use and deny works.
- [ ] Index a benign text file, retrieve a known fact and inspect citation provenance.
- [ ] Confirm stale RAG results are not attached after changing the query.
- [ ] Confirm PDF ingestion refuses when `INDRA_ALLOW_UNSANDBOXED_PDF=false`.
- [ ] If Docker is enabled, run only `python --version` offline before other commands.
- [ ] If remote access is enabled, test wrong token, correct token, logout, token rotation, HTTPS, and access from mobile data over Tailscale.
- [ ] Build/install Android debug APK on a test device; test back navigation, endpoint validation, expired login and offline state.

## Dependency and supply-chain checks

Before a release, in a clean virtual environment with network access:

```powershell
py -3 -m venv .venv-clean
.\.venv-clean\Scripts\python.exe -m pip install --upgrade pip
.\.venv-clean\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-clean\Scripts\python.exe -m pip check
.\.venv-clean\Scripts\python.exe -m unittest discover -s tests -v
```

Also run appropriate current dependency scanning (for example `pip-audit`), Python static analysis, secret scanning and a code review. Resolve or document every finding. Do not blindly upgrade dependencies without running tests and reviewing advisories. Verify Android Gradle dependencies and signing separately.

## Release steps

1. Update `VERSION`, release notes and `STATUS.md`.
2. Review the diff, generated artifacts, `.gitignore` and secret scan.
3. Run all tests and clean dependency install.
4. Run the manual smoke test on a Windows machine.
5. Build Android debug APK and verify on a real device. For distribution, create a protected release keystore outside the repo.
6. Build a source archive that excludes `.env`, local data, logs, databases, backups, virtual environments, keystores, APKs and tokens.
7. Create a private GitHub repository, push a reviewed branch, and verify visibility remains private.
8. Attach release artifacts only after verifying the exact files and their hashes.

## Git safety

Before commit:

```powershell
git status --short
git check-ignore -v .env data logs .venv
# Inspect the full staged diff before committing
git diff --cached --stat
git diff --cached
```

If a secret is committed, deleting it in a later commit is not enough. Revoke/rotate it and follow GitHub's sensitive-data removal procedure.
