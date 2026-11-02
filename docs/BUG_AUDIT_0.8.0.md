# v0.8.0 product hardening and verification report

This report distinguishes implemented safeguards from tests that can only be completed on the target Windows machine with the user's services running.

## Defects addressed

- Workspace traversal previously risked enumerating large dependency/build trees before discarding their files. The inventory/context/search walkers now prune excluded directories during traversal and enforce bounds.
- Secret-like file filtering was not consistently applied to direct read/search/context paths. A shared readability policy now blocks known secret filenames, directories, unsupported file types and symlinks. Common inline credential formats are best-effort redacted from readable text.
- Approved overwrite proposals did not sufficiently protect against files changing after proposal creation. Existing targets now require a captured SHA-256; stale targets and legacy overwrite proposals without a hash are rejected. Backups are verified before replacement and before undo, and undo rejects later edits.
- Browser context construction had an unconnected UI action. Build, preview, explicit one-turn attachment, detach, one-turn clearing and retry recovery are connected end-to-end.
- Malformed model-list responses could become raw type errors. Provider responses are now shape-checked and failures are mapped to actionable provider errors.
- Optional knowledge retrieval is disabled by default and performs only bounded reads against a configured collection. Qdrant mutation is not enabled.
- Concurrent inference admission, saved-conversation turn locking, run states, bounded streaming buffers and structured event records have regression coverage.

## Automated verification performed in this build environment

- Python unit/API regression suite: 42 tests passed.
- Python bytecode compilation: passed.
- Browser JavaScript syntax check (`node --check`): passed.
- Browser interaction smoke test with mocked APIs: build/preview context → attach → send → verify payload → verify one-turn detach passed; zero JavaScript page errors.
- Responsive browser smoke test at 390px viewport: no horizontal overflow.
- Live FastAPI smoke test on loopback: homepage, health, status, settings, workspace inventory, workspace search, knowledge status, metrics and saved conversations returned HTTP 200; workspace search matched a controlled sample file.
- Deterministic adaptive-router smoke evaluation: 5/5 expected routes selected. This is a routing regression test, not a task-success benchmark.
- Release archive: verified with the ZIP integrity check and a clean extraction; the extracted copy passed the 42-test suite, compilation, JavaScript syntax check, and routing regression test.

## Not verified here

- The Windows PowerShell scripts have not been executed on native Windows in this environment.
- No request has been successfully completed against the user's live llama-swap/llama.cpp model; model inference and the exact model's tool-call format remain endpoint-dependent.
- Qdrant retrieval has only been tested against mocked responses, not the user's real collection/vector dimensions.
- Workbench integration is diagnostic metadata discovery only, not an implementation of business actions.
- No load test with many concurrent model runs, GPU profiling, or multi-hour soak test was performed.

## Launch checklist for the target PC

1. Extract into a writable local path, such as `C:\AI\indra_lok_meta`.
2. Run `start_indra.bat`; allow first-run Python dependency installation.
3. Check `logs\server-out.log` and `logs\server-error.log` if health does not go green.
4. Confirm `GET /api/health` shows `ok: true`, app `Indra Lok Meta`, and version `0.8.0`.
5. In Diagnostics, check the llama-swap endpoint and advertised model IDs. Run the separate inference + tool-call smoke test after a model is loaded.
6. Test a read-only project question, a proposed write, approval, and undo on a disposable sample file before using important work.
7. Keep the app bound to loopback; don't expose it to a LAN. Review research exports before sharing.
