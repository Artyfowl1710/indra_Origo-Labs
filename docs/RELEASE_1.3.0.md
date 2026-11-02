# Indra Origo v1.3.0 — Origo Scout and Ori

## Added

- `GET /api/scout/status` advertises Scout's read-only contract.
- `POST /api/scout/run` executes bounded local HTTP probes for route health, response hardening, policy flags, the modality inventory, provider profile visibility, explicit scratchpad contract, conversation-store response shape, amplifier routes, extension registry, sandbox status and permission queue. Evidence is capped; conversation contents, workspace paths and credentials are not returned.
- Diagnostics contains a Scout control and per-check report.
- Ori is a CSS/SVG-free animated character composed in HTML/CSS. It offers a chat prompt and optional break nudges after 50 minutes of visible-tab time. It honors reduced-motion preferences and has a reminder toggle.
- `docs/SOVEREIGN_SI_OS.md` records the product thesis, action contract, Windows architecture, safety levels and staged roadmap.

## Validation

- 137 Python unit tests passed in this development environment.
- Python compileall passed.
- `node --check app/static/app.js` passed.
- `scripts/validate_extensions.py` passed: 12 skills and 0 invalid plugin manifests; plugin endpoints were not contacted.
- In-process Scout report: 12 checks passed, 0 warnings, 0 failures.

## Explicit limits

Scout only verifies selected safe app routes. It is not a complete security audit or browser/system end-to-end test. Ori is not a background Windows agent and does not place orders, access accounts or control the desktop. Local/hosted model inference, browser speech services, Windows 10/11 operation and real integrations were not tested in this environment. The Capsule and Proof Ledger implementations are absent from this source snapshot and remain scaffold-only.
