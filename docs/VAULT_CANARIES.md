# Vault canaries and outbound checks

Indra can register a random marker in a folder you explicitly choose. When the content guard is enabled, registered markers stop the covered model requests and tool calls before dispatch. A canary is a tripwire, not a real credential: never substitute an API key, password or customer record for the marker.

The machine-local registry stores SHA-256 hashes, random IDs, owner fingerprints, labels and creation times. It never stores the marker text. Every profile checks the shared hashes so switching profiles cannot bypass detection; listing metadata is scoped to its owner profile. Blocked attempts append signed `security.canary_blocked` Audit records containing marker IDs and channel/session/turn identifiers, without request text or marker values.

## Explicit setup

Enable `security.untrusted_content_guard: true` in the selected profile and keep the `indra_content_guard` plugin enabled. The local desktop bootstrap enables the guard unless the user has explicitly disabled it. Existing CLI profiles retain their previous behavior. No marker is silently planted in an existing user folder.

From the installed project root, run the following with the actual existing profile and vault folders:

```powershell
.\.indra-python\Scripts\python.exe scripts\manage_canaries.py create `
  --profile-home 'C:\path\to\profile' `
  --vault-folder 'C:\path\to\vault' --label 'Research vault'
.\.indra-python\Scripts\python.exe scripts\manage_canaries.py list `
  --profile-home 'C:\path\to\profile'
```

Setup exclusively creates `.indra-canary.txt`; it refuses to overwrite an existing file or symlink. The CLI prints the file location and ID, never its contents. This filename is excluded from automatic Knowledge ingestion. Deleting or moving the file does not remove its registered hash or protection. There is currently no UI for setup or removal; keep that acceptance item open. No real user vault was modified during verification.

## Covered paths

- Main conversation payload after request middleware and before request observers/debug dumps, plus the execution callback after execution middleware.
- Shared auxiliary sync/async/stream request planning, before retries or fallback planning; Relay physical sync/async/stream paths, including its rewritten provider payload.
- Registry tool arguments, before approval or execution. A detected canary is a refusal, not an approval request, so YOLO and saved approvals cannot authorize its transmission.
- HTTP voice conversation messages, including retrieved Knowledge/history; uploaded transcription payloads and the native Baseten transcription adapter.
- Native Live voice setup, audio/text and Knowledge-result frames through the [local bridge](LIVE_VOICE_BRIDGE.md). The guarded profile refuses direct-provider tokens.

The generic Python plugin hook is `pre_model_request`. It is distinct from the observer `pre_api_request`: a block, invalid directive, callback exception, timeout or still-running worker stops the request. Main-loop policy refusals are non-retryable and do not trigger model fallback. Auxiliary policy refusals do not enter the recovery ladder. The hook does not modify past context or add prompt tokens.

Detection checks nested string values and keys, Unicode normalization and format characters, whitespace separation, percent/JSON escapes and up to two Base64 decoding layers. Structure, text size and decoding budgets are bounded. A registered registry that cannot be read or a payload that exceeds inspection limits stops the covered operation.

## Verification and limits

Tests use isolated profiles, temporary canary/vault files, real plugin discovery, real OpenAI SDK transports and loopback HTTP receivers. Blocked main/auxiliary/voice requests leave zero inference requests at the receiver; clean calls succeed. The fixture rejects nonlocal DNS lookups. Other checks cover signed incident integrity, hash-only persistence, common encodings, concurrent registration, profile metadata isolation, corruption/limits, plugin failure/timeout, explicit endpoint safety and tool refusal under YOLO. These are controlled fixtures, not independent penetration testing or live cloud-model acceptance.

The fallback fixture found two pre-existing routing issues: the OpenRouter auxiliary resolver ignored an explicit endpoint, and cloud vision failures ignored user-configured fallback chains. Explicit endpoints now remain selected, with HTTPS required for remote overrides; explicit vision fallback chains are honored without silently walking ambient accounts. Capability fixtures now supply actual catalogue metadata, and compression boundary tests use the configured minimum instead of assuming 64K.

**Coverage is incomplete.** Other direct SDK/HTTP integrations, TTS, configured outbound webhooks/telemetry and arbitrary programs' network I/O are not all intercepted. No semantic inspection of speech, pixels, encrypted/steganographic content or arbitrary encodings is claimed. The Live bridge catches adjacent text fragments in a bounded session window; split markers across other requests can still evade detection. A command that reads a protected file internally may not contain its marker in its arguments. Trusted plugins and the local OS/account owner can change code, configuration or the registry. A trained classifier, full mandatory result/egress mediation and independent security testing remain open in the [acceptance ledger](PRODUCT_GOAL_ACCEPTANCE.md).

Current local reports: `data/test-results/canary-root-regressions.log`, `canary-core-regressions.log`, `canary-routing-regressions.log` and `canary-final-acceptance.log`. Earlier failed runs are historical diagnostics; the final reruns supersede affected cases.
