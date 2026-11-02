# Desktop startup without local model assets

## Entry-point correction and visible startup, 2 November

The package now uses `entry.cjs` to invoke desktop startup explicitly. A real Electron probe showed `require.main` belongs to Electron rather than the application module; the previous conditional entry check could therefore leave a windowless process running without starting the backend. Earlier fixtures imported the startup function and missed this package-entry regression.

A local startup window appears before Python services start. Service readiness uses shorter polling, bounded wall-clock deadlines and recognizes an existing sign-in gate as a running backend; this displays the normal authentication screen without bypassing authentication. Local inference health still requires successful authenticated health checks.

The corrected package was launched through `start_origo_auto.ps1` on this PC and its actual native overview inspected. The initial window appeared in 363 ms and workspace startup completed in 12,069 ms while parallel acceptance checks were running. These are observations, not a cross-machine performance guarantee. Timing-only startup receipts are appended to the backend log.

Verification: 310 product tests/two skips, nine native lifecycle/readiness/entry/IPC tests and 20 isolated native startup checks passed. The normal Start menu **Indra Origo** shortcut was backed up and repointed to this prepared native build using `scripts/install_current_desktop_shortcut.ps1`; the legacy standalone executable was not rebuilt.

## Optional local inference

The native desktop opens even when its optional local inference engine is unavailable. Missing Qwen files, a missing or unverified Ollama runtime, and a local routing process that exits during startup no longer prevent access to the workspace and Models page.

The app shows one local-inference notice with **Choose model** and **Continue**. Your saved model selection stays intact. You can use an already configured API provider or connect your own server; Indra does not silently select or spend on another provider. An unverified local executable is never started.

Launch normally with `start_origo_auto.ps1`. To locate the local GGUF files elsewhere, supply `-ModelDirectory` with that directory. Restore missing local dependencies and restart Indra when you want to use those models. This change does not download model weights or repair a malformed model.

The desktop still requires the product Python runtime, Electron and built UI. Failure of the application backend itself remains a startup error. This is startup recovery for the optional inference service, not permission to run an unusable app without its backend.

Profile bootstrap now respects the launcher's selected `ORIGO_HOME`; it updates local endpoint metadata and its loopback credential there. It does not overwrite the default profile when another profile was chosen.

## Verified on 2 November 2026

- Isolated Windows launchers with missing/unverified runtimes launch the same profile, preserve its cloud-model configuration byte for byte, and avoid consulting old process ownership records when no engine will start.
- Bootstrap tests protect the other profile's configuration and credentials.
- Two hidden native runs use the actual product entry, actual Python backend and actual built renderer: missing model assets and an owned local service startup failure. Both reach Models after optional onboarding, preserve the saved configuration, display the setup notice and release the backend port on exit: 20 checks passed.
- Product regression: 310 tests completed, two skips. Native startup/IPC contracts: six passes. Required compilation, extension validation and JavaScript syntax checks passed.

Evidence is under local `data/test-results/`: `optional-local-startup-acceptance.json`, `optional-local-startup-native.log`, `optional-local-startup-root.log` and `optional-local-startup-node.log`.

These tests make no provider inference requests and do not establish clean-installer or complete local-model load acceptance.
