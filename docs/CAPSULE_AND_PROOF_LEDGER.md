# Origo Capsule and Proof Ledger — v1.5 prototype contract

These two features are the start of Origo's research-integrity layer. They are deliberately conservative and do **not** yet constitute a replay engine or a universal document-export blocker.

## Capsule

A Capsule is a signed ZIP archive containing a canonical JSON manifest, an Ed25519 signature, the signer's public key, a hash/size entry for every payload file, small allow-listed run metadata, and recent event metadata with content fields omitted.

### User workflow

1. Open **Diagnostics → Origo Capsule**.
2. Optionally enter a run ID that exists in local run history.
3. Explicitly select workspace-relative files, one per line or comma-separated. A blank selection creates a metadata-only Capsule.
4. Create the Capsule, note the signer's SHA-256 fingerprint, download the ZIP, and use **Verify integrity** before trusting it.

### Safety and integrity contract

- Selected payload is capped at 250 files, 20 MiB total, and 20 MiB per file. Archive verification is capped at 600 entries and 50 MiB uncompressed.
- `.env*`, credential/key/certificate files, SQLite/database/log files, dependency/runtime directories, symlinks, traversal paths, oversize files, and files matching common inline-secret patterns are rejected.
- Nothing in a Capsule is executed by verification. This implementation does not unpack an archive to the workspace.
- The private signing key lives in the app's local data directory and is not embedded in the archive. On POSIX, the key is created with owner-only read/write permissions; Windows ACL behavior must still be checked on a real Windows system.
- The archive includes the public key so anyone can verify the signature cryptographically. A self-contained public key is **not by itself a trust anchor**. Preserve/pin the fingerprint through a trusted channel; the UI distinguishes a valid signature from a signer trusted by this installation.
- The signing key is currently a single local installation key, not a hardware-backed key, organization key, or certificate chain. Back it up carefully if continuity matters.
- v1.5 does not replay runs, lock Python/OS dependencies, snapshot datasets automatically, or prove numerical reproducibility. These are separate roadmap items.

### API

- `GET /api/capsules` — list local Capsules and the local signer fingerprint.
- `POST /api/capsules` — create a Capsule from explicit workspace paths and optional local run ID.
- `POST /api/capsules/{id}/verify` — verify manifest, signature, file hashes and local signer fingerprint status; does not execute code.
- `GET /api/capsules/{id}/download` — download a created local Capsule.
- `GET /api/capsules/{id}/receipt` — download a standalone HTML integrity receipt with archive hash, file hashes, signer fingerprint and verification findings; it contains no workspace file contents and is not a scientific-validity certificate.

## Proof Ledger

### User workflow

1. Choose a small UTF-8 text file in the current workspace and paste an exact excerpt.
2. Register the evidence. Origo records a stable ID, source-relative path, SHA-256 digest, exact excerpt, timestamp and scope limitation.
3. Register a claim statement and choose evidence IDs.
4. Run the draft preflight. The linter checks registered claims for literal inclusion in the draft, missing evidence, stale source hashes, and obvious numeric-token mismatch.
5. For claims with attached, non-stale evidence and no detected numeric mismatch, a user can record an explicit human-review attestation. Unsupported, stale, or numerically mismatched claims cannot be cleared by clicking “review”.

### What it does and does not prove

- An excerpt matching a file proves that the excerpt was present in that file at the recorded hash, not that the statement is true.
- Numeric-token matching is lexical. It is not a unit-aware calculation, statistical test, semantic entailment model, citation verifier or truth detector.
- Every relevant claim must be registered manually; v1.5 does not automatically discover every factual claim in arbitrary prose.
- “Reviewed by human” is an attributable workflow attestation, not a guarantee of truth.
- The preflight result is **not yet wired into every document/slide/spreadsheet exporter**. Treat it as a review tool, not an export-security boundary.

### API

- `GET /api/proof/ledger` — retrieve the recent local evidence/claim records.
- `POST /api/proof/evidence` — register an exact excerpt of a local workspace file.
- `POST /api/proof/claims` — register a claim and its evidence IDs.
- `POST /api/proof/claims/{id}/review` — record or revoke the user's explicit review attestation.
- `POST /api/proof/lint` — lint registered claims against draft text. The response explicitly states that exporters are not globally gated yet.

## Critical future tests before a research-grade claim

- Cross-machine verification with a pinned external signer fingerprint.
- Windows private-key ACL inspection and recovery/rotation tests.
- Crash/interruption tests during archive creation and concurrent evidence registration.
- Manifest malformed-input, duplicate-entry, ZIP-bomb, symlink, and tampering fuzz tests.
- Replaying a trivial deterministic Capsule in a disposable no-network sandbox; compare artifact hashes and report non-determinism rather than silently treating it as failure-free.
- Lint integration into every supported exporter, with tests demonstrating that an unsupported claim prevents a “verified” export.
- Statistical claim helpers with repeated seeded runs, confidence intervals, multiple-comparison caution and source links.
