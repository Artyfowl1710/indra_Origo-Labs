# UI and OpenRouter update · 2026-10-30

## Included

- Persistent light and dark themes, with a visible header switch and command-palette action.
- A composer privacy indicator that updates when the active provider profile changes.
- Updated navigation, chat landing area, cards, controls, and color tokens. Light mode uses violet and coral accents; dark mode uses mint and violet accents.
- A CSS-rendered, dimensional Ori companion. Motion follows the existing reduced-motion preference and companion reminders remain optional.
- A one-shot OpenRouter compatibility script that prompts for a temporary key without echoing it or saving it.

The [dark dashboard](https://dribbble.com/shots/25683483-Dashboard-UI) and [light task dashboard](https://dribbble.com/shots/25241984-Task-Management-Dashboard) were visual references, not copied assets.

## Verification

- `python -m compileall -q app scripts tests`: passed.
- `node --check app/static/app.js`: passed.
- `python scripts/validate_extensions.py`: 12 valid skills; no invalid plugin manifests.
- HMI static audit: 24/24 checks passed.
- Source scan for an OpenRouter key and PEM private-key headers: no matches.
- Live OpenRouter test: the requested model was advertised and Origo's provider adapter received `ORIGO_OK` from a bounded request.

The full Python suite could not complete in the temporary pinned `.venv` because Windows Application Control blocked the downloaded Pydantic binary. The temporary `.venv` was removed. The machine's global Python has incompatible FastAPI and Starlette versions. Browser visual QA was blocked by the environment's browser URL policy. These are verification gaps, not passing test results.

## Security boundary

The test key was supplied through a hidden terminal prompt and was not written to this package. Treat any key pasted into a chat as exposed and rotate it after testing. Selecting the hosted profile sends prompts and attached context to OpenRouter and its serving provider. Local inference stays the default.

The UI update does not add OS control, bypass approvals, or establish a security certification. A clean Windows test environment, real browser accessibility review, Android build, and independent security review are still needed before a release claim.
