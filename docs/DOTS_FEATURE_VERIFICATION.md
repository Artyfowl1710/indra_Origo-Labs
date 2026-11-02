# Dots/OpenRouter feature verification · 2026-10-30

Overall release gate: FAIL / incomplete. Do not advance to local-model acceptance based on these results.

## Passed

- Live imported Indra AIAgent with dots-studio/dots-3-note-preview:free: exact-response chat and disposable fixture retrieval via file tools both passed. Results: data/test-results/dots-live.json. The temporary key was supplied through a hidden prompt and not saved in source or reports. The first test utility process exited with a Windows temporary-log cleanup error after both checks passed; handler shutdown was added to the utility, but that cleanup change has not been reverified.
- Customized dashboard automated suite: 300 passed, 0 failed using two workers and a 20-second test timeout. Earlier unrestricted parallel runs hit resource-related timeouts. Results: data/test-results/web-tests-final.json.
- Original Origo regression suite: 190 tests ran, 0 failures/errors, 2 skipped. Log: data/test-results/origo-regression.log.
- Imported dashboard/approval/file-safety/document-skill/voice-limit subset: 216 passed, 3 Linux-only checks skipped on Windows. This does not verify the skipped POSIX behavior.
- Disposable DOCX, PDF, PPTX, XLSX generation: all four passed container/signature checks; DOCX content, PPTX slide existence and XLSX numeric cell content were checked. This is functional validation, not a visual-quality review. Results: data/test-results/document-tests.json.
- Python compilation, existing JavaScript syntax check, native-shell JavaScript syntax, and extension validation passed.

## Fixed in the Origo copy

- Copied tomllib compatibility shims shadowed Python 3.13's stdlib module and exported no parser. They now load the standard-library package correctly.
- Destructive confirmation dialogs now expose role=alertdialog, matching the session-delete interaction and accessibility contract.
- Three tests for POSIX event-loop/Unix-temp-path behavior were marked Linux-only, following the source repository's native-host testing rule. They remain unverified here.
- Restored the reference root ignore file to the imported source layout; the reference itself is unchanged.
- Installed missing test/document/PDF dependencies into the isolated Origo Python environment. These environment changes still need to be captured in reproducible release packaging.

## Failing or incomplete

Broader imported API/build tests are not green. The focused rerun still shows ten failed assertions across profile/gateway state and web-build behavior, plus an auth-state cleanup error in a topology test file. Complete retained diagnostics: data/test-results/api-failures.log. Another POSIX-only build-lock test imports fcntl, unavailable on Windows; it needs proper native-host classification rather than a success claim.

The passing chat and file retrieval checks are live Dots integration tests of the imported agent, not proof that every GUI action works with Dots. Live GUI chat attachment flow, cancellation and recovery, full edit/review/apply/undo flow, document generation invoked by the model, local microphone transcription, speech playback, Docker sandbox execution, RAG ingestion/retrieval with the configured library, installer upgrades/uninstall, and independent security testing remain incomplete. No user microphone content was captured. No local-model test was run in this phase.

Original working SIH-26-main files were read only. Runtime fixtures and generated reports stay under ignored data/test-results and must not enter source archives or commits.
