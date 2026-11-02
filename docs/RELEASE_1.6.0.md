# Indra Origo v1.6.0 — Outcome Review and HMI Guardrails

## Added

- Per-answer calibration note clarifying that traces and linked evidence aid inspection but do not guarantee correctness.
- Optional per-answer feedback: Useful, Incorrect, Incomplete, or Risky / unsafe.
- Ratings can be changed, individually removed, or cleared in bulk. Removing ratings never deletes run/conversation data.
- Local Run History summary with the count per label and explicit disclosure that ratings are self-reported, not an objective model-quality score.
- Content-free persistence: rating records contain run/conversation IDs, one allowlisted label, and timestamps. No prompt/answer text is stored in the feedback table. Ratings are not sent to the model, used for training, or used for automatic behavior adaptation.
- HMI Quality Gate checks for optional/clearable feedback and transparent rating data flow.
- Expanded regression tests for run membership, invalid input, no model-call side effect, clear/remove behavior, and conversation deletion cleanup.
- HMI and agent behavior matrix covering when to act, ask permission, stop, recover, or avoid manipulative UX.

## Verification completed in the release workspace (2026-10-29)

- **170 Python tests passed** (`python -m unittest discover -s tests -q`).
- Python compilation passed (`python -m compileall -q app tests scripts`).
- Browser JavaScript syntax passed (`node --check app/static/app.js`).
- Extension validation passed: 12 skills, one disabled example plugin manifest, zero invalid manifests; no plugin endpoint was contacted and no skill was executed by the validator.
- API smoke check: `/`, `/api/health`, `/api/status`, `/api/hmi/audit`, `/api/feedback`, `/api/capsules`, and `/api/proof/ledger` each returned HTTP 200 in an isolated TestClient run.
- HMI Quality Gate: **24 checks, 0 failures**. This is a static source audit only.
- New feedback tests exercise valid/invalid IDs and labels, run/conversation matching, editable single-rating semantics, per-conversation label scoping, local data-flow promises, no provider/model invocation, deletion, clear-all, and cascading cleanup.

Native Windows UI automation, real Chromium click-through, keyboard/screen reader checks, live-provider inference, Windows ACL tests, and a moderated usability study were not performed in this environment.

## Scope limits

Outcome Review is a local feedback log, not an automatic learning mechanism, model benchmark, calibrated confidence estimate, or research-grade user study. The HMI static audit is a source heuristic and is not WCAG conformance certification. No guarantee is made that this product will win a hackathon or award; those depend on judging criteria, execution quality, competitors, and evidence shown during the demo.
