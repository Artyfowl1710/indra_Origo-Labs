# Indra Origo Tool Contract

The harness is the authority for whether a model tool call may run. Tool descriptions are guidance only; implementations must independently validate every argument and permission.

## Capability families

- **Workspace read:** list files, inspect bounded text, search symbols/text, build bounded context packs, inspect Git status. Scope: selected workspace; sensitive paths and symlinks are blocked.
- **Write proposals:** propose new or changed text files. No direct model write. Approval checks the current content hash and creates a verified backup before an approved overwrite.
- **Web research:** search, fetch, research and same-host crawl public pages. Every agent-initiated request requires the permission broker. Manual requests require a separate user confirmation. URL validation and robots policy are defense in depth, not a network firewall.
- **Plugins:** explicitly enabled manifest-driven tools that call numeric-loopback JSON services. Manifest read-only claims are not proof of side-effect-free behavior.
- **Docker sandbox:** command is an argv list, no shell string. Disposable sanitized copy, resource limits, no network by default, no host directory mount and no automatic workspace write-back. Network-enabled runs require a separate per-run approval.
- **Research Studio:** only the fixed built-in synthetic-data Optuna baseline runs in the host app. User-authored experiment files must run inside the opt-in Docker sandbox.
- **Artifact return:** only user-requested relative paths with allowed extensions and size caps are copied from an ephemeral sandbox output into the local app data artifact store. This is not project write-back.
- **Task graph:** bounded DAG of read-only child agents. Validate graph schema/cycles before model calls. Child results are untrusted context and do not authorize actions.

- **Proof Ledger:** evidence entries bind a claim to an output digest, command argv, seed and run identifier. Numeric values must exist in the selected output. Source capture requires a separate explicit network consent and a verified saved snapshot. Linting is strict but cannot prove semantic entailment. Never fabricate ledger IDs.

## General invariants

1. Validate data at each boundary; never trust model-supplied paths or tool arguments.
2. Enforce time, step, output, concurrency and storage budgets in code.
3. Do not pass secrets to the model, website, plugin or child agent unnecessarily.
4. Keep user data out of telemetry by default; record metadata rather than entire prompts or source files.
5. Do not claim completion until the operation returns and the result is checked.
6. Every new tool should have success, failure, timeout, malformed-input and permission tests.
