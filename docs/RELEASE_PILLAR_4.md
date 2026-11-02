# Indra Origo v1.2.0 — Pillar 4 implementation notes

## Added

- Capability inventory endpoint (`GET /api/capabilities`) that explicitly separates client implementation from upstream model capability verification.
- Switchable `local` and optional `hosted` OpenAI-compatible provider profiles. Local remains the startup default. Hosted profile reads `INDRA_HOSTED_BASE_URL`, `INDRA_HOSTED_API_KEY`, and `INDRA_HOSTED_MODEL` from `.env`; hosted URLs must use HTTPS, and keys never appear in API responses. Switching profiles makes no model call.
- User-visible provider-profile control and capability diagnostics view.
- Bounded chat attachments: up to 4 files, 5 MiB each, 6 MiB combined binary payload. Text/code content is passed as untrusted context. PDFs are parsed with `pypdf`, capped at 40 pages and 24,000 extracted characters. Images are forwarded only after a per-message UI opt-in and strict supported-MIME/signature checks.
- Local browser previews for text/code, PDF, image, audio and video files.
- Browser SpeechRecognition dictation and SpeechSynthesis read-aloud, with stop controls and explicit privacy wording.
- Persistent project scratchpad for explicit notes/hypotheses/open questions; it is not automatically injected into model prompts and is not hidden chain-of-thought.

## Test results

`python -m unittest discover -s tests -q` — run before release packaging; 134 tests passed in the validated source checkout.

`python -m compileall -q app tests scripts` — run before release packaging.

`node --check app/static/app.js` — run before release packaging.

`python scripts/validate_extensions.py` — run before release packaging.

## Not yet done

This release does not provide offline ASR/TTS, audio/video understanding, OCR for scanned PDFs, video frame extraction, accessibility/DOM conversion, headless screenshot visual repair, provider-native constrained decoding, or real-provider capability verification. Browser speech recognition may use the browser vendor's service. Hosted profile is a generic OpenAI-compatible seam, not a claim that Baseten or OpenRouter was tested. Do not switch to the paid profile until the local gateway has passed the model smoke test and a small evaluation set has been run.
