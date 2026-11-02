# Indra Origo v1.4.0 — HMI quality gate and command palette

## Added

- **Command palette:** Ctrl/Command+K opens a searchable action list; Escape closes it; arrow keys move the selection; Tab remains inside the dialog; focus returns to the opener. It provides navigation to workspaces, Scout, the HMI audit, quick-capture scratchpad and Focus Mode.
- **Focus Mode:** hides the sidebar to reduce visual chrome. It remains reversible through the keyboard-accessible command palette and remembers the user's explicit preference locally.
- **HMI Quality Gate:** read-only `/api/hmi/audit` endpoint and Diagnostics report with 15 source-level heuristics covering document identity, focus indication, reduced motion, selected design-token contrast, live status feedback, command discovery, input labels, approval boundaries, companion reminder control, autoplay and manipulative urgency, cancel path, bounded quick-start count, error recovery and data-flow disclosure.
- **Adversarial regression fixtures:** tests prove the audit flags deliberately broken labels/focus routes, low-contrast tokens, autoplay media and urgency/scarcity copy.
- **Product design charter:** `docs/HMI_AND_PSYCHOLOGY.md` lays out agency-first engagement, transparency, error prevention/recovery, accessibility, and real-user validation requirements.

## Validation

- `python -m unittest discover -s tests -q`: **143 tests passed**.
- `python -m compileall -q app tests scripts`: passed.
- `node --check app/static/app.js`: passed.
- `python scripts/validate_extensions.py`: 12 skills valid; 0 invalid plugin manifests; no plugin endpoints contacted.
- Live TestClient smoke checks: `/`, `/api/status`, `/api/health`, `/api/hmi/audit`, `/api/scout/status` returned HTTP 200; HMI static gate returned **15 passed, 0 warnings, 0 failed**.

## Not verified

A real Chromium navigation attempt was blocked by the environment with `ERR_BLOCKED_BY_ADMINISTRATOR`, so rendered browser interactions and the command palette's actual keyboard/focus behavior were **not** verified end-to-end in this environment. No real screen-reader test was run. HMI source checks are not a formal WCAG conformance report, do not measure every rendered contrast pair or target size, and do not establish usability. No model inference or hosted API calls were made.

## Safety boundary

No email, commerce, delivery, or OS-wide automation connectors were added in this increment. Command palette entries do not grant permissions, approve writes, or bypass existing action boundaries.
