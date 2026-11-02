# Automatic local image routing

Default launcher: double-click `start_origo.bat`. Its `start_origo_auto.ps1` opens the customized Indra desktop and owns an authenticated loopback inference gateway. This is an integration build; `start_origo_cpp.ps1` remains available for direct-model diagnostics.

```powershell
.\start_origo_auto.ps1 -Device auto
# Explicit CPU mode:
.\start_origo_auto.ps1 -Device cpu
# Optional model directory:
.\start_origo_auto.ps1 -ModelDirectory 'D:\Models' -Device gpu
```

The directory must contain Qwen3.5-4B-Q4_K_M.gguf, Qwen2-VL-OCR-2B-Instruct.Q4_K_M.gguf, and mmproj-Qwen2-VL-2B-Instruct-f16.gguf. The launcher uses the previously installed signed Ollama distribution's llama-server.exe. Models remain outside the distributable source tree.

The gateway keeps a stable endpoint. An image-bearing user turn selects the vision model/projector, obtains an observation, then selects the text model for the agent response. Tool schemas and stored messages remain untouched. A single lease covers both stages and the response stream. The text model remains resident for follow-up text. Serial switching uses less GPU memory at the cost of model-loading latency.

Select `origo-auto` for attachments; explicitly selecting `origo-qwen35` rejects images with an actionable error. Accepted image formats are PNG, JPEG and WebP, with at most two attachments, 8 MiB each and 16 megapixels each. URL and file fetching through image references is prohibited. Prior attachments are represented as earlier-image notices on the wire; fresh reanalysis requires another attachment. Persistent observation receipts/history restoration need additional integration.

Each launch generates a new random local token. The named `custom:origo-local` provider reads it from the isolated `data/indra-auto-home/.env` profile, which is runtime state excluded from releases. No cloud key is needed. The inference gateway rejects browser origins and requires its token on every endpoint. The desktop's parent-process watcher shuts down its gateway/model when the desktop exits. Forced termination, crash recovery and concurrent desktop-instance ownership still require further acceptance tests.

## Verification on 31 October 2026

- 13 gateway/image/lifecycle contract tests passed: invalid inputs, URL rejection, authentication, origin rejection, MIME mismatch, concurrent serialization, streaming, cancellation cleanup, CPU fallback and missing model/runtime behavior.
- Five imported-agent tests passed, including real named-provider resolution from an isolated profile and endpoint/credential separation.
- Required Origo checks passed: 203 tests, two skips, compilation, extensions and JavaScript syntax. The customized UI production build passed.
- Real GPU route: vision → text returned the visible identifier in approximately 11.6 seconds; subsequent text completed in approximately 0.94 seconds in that synthetic probe.
- Real CPU route: vision → text took approximately 22.5 seconds; subsequent text approximately 3.96 seconds. These are individual probes, not general latency guarantees.
- **Exact OCR acceptance failed:** the image says `INDRA42`, but the vision model reports `indra42`. The test intentionally remains red rather than normalizing away the case error. Routing success does not establish reliable transcription.

Full desktop attachment, streaming cancellation, queue saturation, mobile pairing, clean-machine installer, voice and benchmark coverage remain open. See PRODUCT_ACCEPTANCE.md for the full product scope.

Crash recovery update: model and sharing supervisors now require strict Windows jobs and explicitly assign owned native children by their creation handles. A real isolated signed CPU model crash probe verified that owner death reaps the server and closes its health endpoint without terminating an unrelated process. See RUNTIME_PROCESS_OWNERSHIP.md for evidence and Python-runtime compatibility limits.

Follow-up end-to-end evidence: the actual running desktop backend's authenticated WebSocket chat protocol passed a greeting with zero tool calls (18.76 seconds cold) and an image attachment with the exact `INDRA42` response and zero agent tool calls (20.41 seconds). Receipt: `data/test-results/automatic-desktop-backend.json`; probe: `scripts/test_auto_desktop_backend.py`. This validates the attachment/session/agent/gateway path, but does not erase the separate minimal-probe capitalization failure. Native click-based acceptance was limited by the computer-use helper reporting unavailable input geometry.
