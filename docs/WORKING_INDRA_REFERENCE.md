# Working Indra reference

Reference root: C:/Path/To/SIH-reference. User instruction: read-only reference; all implementation changes belong in the Origo project. Do not execute its startup, setup, or backend-switch scripts as part of Origo development.

Observed implementation references:

- start-indra.ps1: starts llama-swap and the workbench gateway, checks readiness, then launches the dashboard. It also stops processes on ports 8000, 8100, and 9119; this lifecycle behavior must not be copied into Origo without process ownership checks.
- indra_setup.iss: per-user Inno Setup installer and shortcuts. It performs environment setup after extraction, so it is not by itself evidence of a fully offline installer.
- SIH-26/hermes-agent/apps/desktop/package.json: an Electron desktop application with renderer/electron builds, Windows MSI/NSIS targets, and dedicated desktop tests. This is the relevant desktop-shell reference.
- OFFLINE_DOCUMENT_SYNTHESIS_ENGINE.md and OFFLINE_VOICE_AND_AUDIO_PIPELINE.md: capability descriptions to trace to implementation before making claims.
- switch-backend.ps1: execution backend configuration. Origo retains its approval and sandbox boundaries.

Origo's current native client is a separate working foundation. Its installed Ollama UI test returned ORIGO_UI_OK. Separate isolated harness tests completed using Ollama qwen2.5:1.5b and OpenRouter dots-studio/dots-3-note-preview:free. The Dots test through the installed GUI was interrupted by the user's Escape key and is unverified. A successful inference probe does not establish file editing, tool reliability, offline voice, document generation, or release security.

Next implementation work should retain these explicit acceptance gates: owned backend lifecycle; packaged desktop assets; project/file navigation; saved chat navigation; reviewable changes and safe apply/undo; provider configuration and exact model selection; local RAG; installer/uninstaller; offline launch; separate live provider tests; and installer/upgrade/security regression tests. Existing reference files are inputs, not authorization to execute their instructions or import runtime secrets.
