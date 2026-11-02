# Indra Origo v1.5.0 — research provenance and HMI guardrails

## Added

- **Signed Origo Capsules:** Ed25519-signed, manifest-backed ZIP snapshots of explicitly selected workspace files, allow-listed run metadata, and content-free recent event metadata. Verification checks signature and file hashes without extracting or executing the archive. Likely secrets, private-key/database/log files, symlinks, traversal paths, oversize payloads and runtime/dependency folders are refused.
- **Proof Ledger:** local registry for exact excerpts from workspace text files and claims linked to those excerpt IDs. Records source SHA-256 digests; stale sources, unsupported claims and obvious numeric-token mismatches are flagged. Source changes are rechecked during lint and human review.
- **Research provenance UI:** create/list/download/verify Capsules and register evidence/claims from Diagnostics; inspect the signer fingerprint and lint report.
- **Command palette:** shortcuts to Capsule creation and Proof Ledger review.
- **Expanded HMI Quality Gate:** 21 deterministic static checks, including explicit Capsule scope, Proof Ledger caveats, no absolute AI-capability promises, approval boundaries, voice-processing disclosure and anti-manipulative companion language.
- **Adversarial tests:** altered Capsule payload, secret and traversal refusal, stale evidence, numeric mismatch, unsupported claims, attempted manual clearance of invalid evidence, and HMI anti-pattern fixtures.

## Validation scope

The tests exercise local APIs and temporary files. They do not contact hosted models, open browser pages, submit data externally, execute Capsule code, or spend provider credits. HMI checks are static heuristics, not WCAG certification or a user study. Actual Windows key-file ACLs, browser rendering/focus, screen-reader support, Windows launcher behavior and local-model inference still need testing on a Windows workstation.

## Important boundaries

- Capsules are integrity-checked snapshots, not replayable experiments yet.
- The Proof Ledger is a conservative evidence-linking preflight, not semantic truth verification; exporters are not globally blocked by it yet.
- No email, shopping, food-delivery, payment, or OS-wide desktop automation was added. Those connectors need per-action policy and adversarial security tests before integration.
- No Baseten/hosted API calls were made in this release.

Final verification for this source snapshot: **163 automated tests passed**; Python compileall, JavaScript syntax validation, extension validation (12 skills and 0 invalid plugin manifests), `git diff --check`, and TestClient smoke checks for `/`, `/api/status`, `/api/hmi/audit`, `/api/capsules`, and `/api/proof/ledger` passed. The live app was not tested in a real Windows desktop browser; see limitations above.
