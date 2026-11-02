# Database runtime safety

Indra selects journaling using the SQLite library linked to its actual Python executable. The current desktop runtime reports SQLite 3.50.4, so product databases use rollback journaling (`DELETE`). Affected SQLite versions have a rare WAL-reset race; the documented fixes are 3.51.3 and later, with 3.44.6/3.50.7 backports. See [SQLite's explanation](https://sqlite.org/wal.html#walresetbug).

## Policy and migration

The shared product opener covers legacy application state, Knowledge, signed Audit, content-exposure tracking, canary hashes, project grants and conversation records. On affected or unknown versions it requires `DELETE`. On documented fixed versions, stores that previously preferred WAL can use it; project grants and conversation records retain rollback journaling. Filesystems that cannot enable WAL can fall back to `DELETE` on fixed engines.

Every new connection checks the effective mode and sets `synchronous=FULL`. Mode changes go through SQLite's own journal transition; Indra never deletes WAL/SHM/journal files to force a migration. Existing schema, documents, settings, grants, record IDs, canary hashes, signing keys and signed events are retained. This prevents the documented runtime hazard; it does not repair unrelated pre-existing corruption or make disk/hardware failures impossible.

An active old connection can prevent transition. In that case the affected operation refuses to open safely and explains that other Indra instances should be closed before retrying. There is no silent unsafe-WAL fallback, database reset, key rotation or automatic file replacement. Preserve unsent work before closing an app. No live user draft was discarded for this change.

Check the installed runtime from the project root:

```powershell
.\.indra-python\Scripts\python.exe -c "import sqlite3; from app.sqlite_safety import journal_mode; print(sqlite3.sqlite_version, journal_mode())"
```

The core agent already has its own version-aware state-database policy. This update brings the product stores under equivalent version boundaries. A global Python upgrade does not prove that the packaged executable's SQLite changed; clean installer acceptance must check the actual bundled runtime.

## Audit verification

Local sequence, previous-digest and event-digest validation now use explicit runtime checks. Python `-O` cannot disable them. A subprocess test retains valid signatures but moves their database sequence numbers; both normal and optimized verification reject the ledger. The separate checkpoint verifier opens existing databases read-only and refuses a missing file without creating a new empty ledger.

Local signatures alone do not prove custody against an owner who can replace both the database and signing key. Retain signed checkpoints independently to detect rewriting/truncation. The runtime check in this pass created a fresh checkpoint and ran the separate verifier against it; that proves current consistency, not independent custody of an older checkpoint.

## Verification and remaining work

Nine new storage tests cover version/backport boundaries, safe mode/full sync on reopened connections, WAL migration with retained data, busy migration refusal/recovery, corruption refusal, handle cleanup, all seven product stores, multi-process Audit writing and abrupt writer termination. Four worker processes produced 48 verifiable signed events. The crash fixture forced a large uncommitted write and retained the earlier committed value after reopening.

Current results: 286 root tests/two skips, 58 focused core tests across workspace/Knowledge/content policy/voice/canary paths, 28 isolated native controls/records/theme checks and required compile/extension/JavaScript gates. All seven existing databases inspected in the running desktop reported `DELETE` and passed SQLite quick checks. Its 148-event signed Audit and the separate checkpoint verifier passed; the signing key was unchanged. These figures describe the captured snapshot, not a permanent event count. The user's running window and draft were left untouched.

Evidence: `data/test-results/sqlite-policy-tests.log`, `sqlite-policy-root-tests.log`, `sqlite-policy-core-tests.log`, `sqlite-policy-native-run.log` and `sqlite-policy-runtime-acceptance.json`. Fixtures use temporary synthetic data; no user database was deliberately corrupted or crash-tested. Independent security review, clean installation/packaged runtime acceptance and the rest of the [product goal](PRODUCT_GOAL_ACCEPTANCE.md) remain open.
