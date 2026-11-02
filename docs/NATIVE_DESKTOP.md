# Native desktop build · 2026-10-30

Run Indra Origo from the Windows Start menu. The installed executable includes Python and runs the bounded harness directly; no browser or web server is required.

Choose Ollama and an installed model (tested: qwen2.5:1.5b), or OpenRouter and dots-studio/dots-3-note-preview:free. OpenRouter keys are held only for the current process. Choose a project folder before asking about files. Ctrl+Enter sends; Cancel cancels the current run. Light/dark appearance, new chat, and Markdown chat export are available.

Verified: Windows executable built, installed, and opened; isolated harness inference completed with ORIGO_OK separately using local Ollama and Dots/OpenRouter. Python and JavaScript compilation and extension validation passed. These bounded checks do not establish tool-calling reliability or security certification.

Current native client limits: edit proposals cannot yet be reviewed/applied in this client; web/plugin/sandbox actions are denied; there is no conversation browser, native RAG manager, or mascot here. The complete older interface remains separate. Full regression verification is still blocked by the existing FastAPI/Pydantic test-environment problem. This is a working desktop foundation, not the completed product roadmap.

Offline installer: extract the desktop ZIP, then run install_desktop.ps1 in PowerShell. It installs under LocalAppData/Programs/IndraOrigo and creates a Start menu shortcut. It needs no Python or package downloads. Ollama and model weights must already be installed for offline inference. OpenRouter needs internet. No antivirus exclusions are required by the installer. This build is unsigned.
