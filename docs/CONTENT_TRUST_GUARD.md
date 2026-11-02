# Tool content and one-operation review

Indra's local desktop profile enables `security.untrusted_content_guard: true`. The existing explicit `false` setting is preserved. Other CLI profiles retain their previous behavior unless enabled. The setting changes tool policy, without rewriting past conversation messages or the cached system prompt.

The guard marks a session/turn before a tool result can arrive, including concurrent reads. Retrieved document envelopes, retained tool history and media parts in main-model requests also mark exposure. Pure local read-only retrieval stays available. Later shell commands, writes, network requests, sends and unknown extension tools require review; existing scope restrictions and tool approvals continue to apply. New/unknown tools are not automatically classified as read-only.

Review is **one operation**. Saved allow rules, YOLO and unattended approve settings cannot replace a person at this boundary. No reviewer means no execution. Denial, timeout, policy/storage error and invalid decisions stop the action. The desktop offers **Approve (Once)** and **Deny / Reject**, including after reconnecting to a pending request. Legacy clients returning a broader choice still authorize only that operation, without saving consent. Concurrent requests have distinct correlation keys. A conflicting plugin argument rewrite is blocked rather than approved using a different payload.

The profile keeps a local exposure ledger and signed Audit events for exposure, tool-result quarantine, requested review and review answers. Argument and result hashes identify the evaluated payload without copying source content into Audit. The review panel includes the relevant command/path/recipient details; document text and API keys do not become an extra Audit transcript.

Registry tool results are screened by the existing bounded offline rule scanner, including JSON keys and values. Matching text is withheld. Clean JSON dictionaries keep their original fields and receive an untrusted-evidence marker; structured media/list formats are preserved. Very large results are quarantined instead of parsed without a bound. A failed read remains conservatively marked. A new turn that retains untrusted tool history is marked again.

## Limits and remaining work

Registered vault canaries now veto covered main/auxiliary/HTTP-voice payloads and registry tool arguments. See [Vault canaries](VAULT_CANARIES.md) for explicit setup, verification and uncovered paths. This is separate from the observer used to mark exposure.

This is a policy boundary and a heuristic text filter, not a complete prompt-injection or DLP system. It does not inspect image pixels or audio meaning, intercept every file read inside a shell program, or scan all inline/memory-provider return paths. Trusted extensions can execute arbitrary code and remain part of the trusted computing base. The host's general result-transform hook is best effort on timeout; the separate pre-tool action gate still marks exposure and requires review. A trained offline classifier, mandatory policy filtering across every result path and blocking across every outbound integration remain open. The API observer used to mark media exposure is **not** an outbound veto.

## Verification and Windows fixes

Tests exercise real plugin discovery, SQLite/profile isolation, concurrent reads, hostile JSON/plain text, a real file read and a controlled side-effect handler. They verify denied actions leave no side effect, approved actions execute once, broad client replies never persist, cached/YOLO/unattended settings cannot bypass review, and gateway replay retains the restricted choices.

The local-Qwen/Docker project fixture runs with the guard enabled. Its automated reviewer is allowed to approve only edits to the fixture invoice module and exact test/read commands; it is not a human-operated trial. An isolated native renderer checks the pending request identity, visible choices and signed approval receipt. Results are in `data/test-results/real-project-goal-guarded/acceptance.json`, `content-guard-native-acceptance.json` and `content-guard-*.log`.

This exercise also exposed Windows path issues. Linux container paths now use POSIX absolute-path rules on Windows/Python 3.13. Re-registering a mounted project during goal continuation preserves the live container directory. Changing to another host mount refuses execution until a fresh chat/sandbox is started. Opening and closing a second chat viewer preserves the original connected window. The goal judge now receives bounded, redacted runtime check evidence instead of relying solely on the assistant's claim that tests passed.
