# Repository guidance for coding agents

- Product name: Indra, by Origo Labs. Keep this identity consistent in user-visible UI, docs and scripts; retain required upstream notices and internal compatibility identifiers.
- Windows-first and local-first. No network service should bind beyond loopback by default.
- Preserve the default-deny / approval-first safety model. Never add host-shell fallback to Docker execution.
- Keep optional integrations optional and report unavailable services clearly.
- Run `python -m compileall -q app scripts tests`, `python -m unittest discover -s tests -v`, `python scripts/validate_extensions.py`, and `node --check app/static/app.js` after changes.
- Add tests for every new API contract, especially path traversal, missing dependencies, invalid JSON, permission failure, output limits and concurrency.
- Avoid secrets and user runtime state in project archives: do not commit `.env`, `data/*.sqlite3`, logs, artifacts, workspace files, `.venv`, caches or model weights.
- Scientific claims must be sourced; synthetic scores are product smoke tests, not research evidence.
