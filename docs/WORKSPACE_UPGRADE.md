# Indra workspace update — 31 October 2026

The product is **Indra**, by **Origo Labs**. Start it with `start_origo.bat`; the desktop starts its own loopback backend. Opening an HTML file directly is not a supported launch method. The original SIH reference folder is unchanged; its existing model weights are read by the local launcher.

## Start page and appearance

The desktop opens on a city hero using the supplied video and image, stored locally. Video is silent, loops, pauses offscreen, offers a pause button, and respects reduced-motion preferences. The hero composer carries a draft into Chat for review. Origo Blue, Origo Ember and Origo Teal share semantic colors with dialogs and controls. Ambient city lines and fireflies are decorative and do not intercept input.

Conversation Mode now shares the selected theme, traps keyboard focus and restores focus when closed. Device voice selection remains available. Transcription and model requests use the configured providers; a cloud provider requires a network connection. UI verification does not establish microphone, speaker or transcription accuracy on every device.

## Models and connection state

The local catalog exposes three distinct choices:

| Choice | Role |
| --- | --- |
| Indra Auto | Routes fresh images through Qwen2-VL OCR, then Qwen coding |
| Qwen3.5 4B | Text and coding agent; rejects direct image input |
| Qwen2-VL OCR 2B | Direct image reader without agent tools |

Connection checks prefer the selected provider endpoint over obsolete workbench configuration. Cloud credentials being configured is reported separately from an inference health check. Provider quota and supported API methods still determine which cloud models can run.

## Knowledge and project folders

Knowledge supports batches of up to 32 files, 7 MiB per file and 32 MiB total. It combines SQLite FTS5 lexical retrieval with normalized 384-dimensional MiniLM vectors and source labels. The pinned, quantized ONNX embedding weights are approximately 23 MB and stay on the CPU. After the explicit one-time download, embedding and retrieval require no network. Restore assets on another machine with `python scripts/install_embedding_model.py`; install `requirements-local-runtime.txt` in that machine's product environment first.

Use Projects in Chat to grant a specific folder. Granting starts indexing; active projects refresh periodically and offer a manual index button. Unchanged files are skipped, changed files replace their old chunks, and deleted files are pruned. Projects have separate indexes. Switching projects starts a fresh chat and uses that folder as its working directory. The file browser previews supported text and document content.

Folder grants select context and a working directory; they are **not an operating-system sandbox**. Existing tool permissions and approvals still apply. Known credential names, signing files, junctions and build folders are excluded. These checks are not comprehensive data-loss prevention. Only grant folders you intend the agent to use.

Limits include 2,000 scanned files per project, bounded extraction, and a small English-focused embedding model. PDF text, DOCX, XLSX and PPTX extraction is supported; scanned PDFs need OCR, and spreadsheet extraction is basic text rather than a formula engine. Unsupported binary files are skipped. Chat attachments are passed together to the agent but are not silently persisted into Knowledge. Index documents through Knowledge or a project for later retrieval. When resuming a project conversation, select the same project to retain its retrieval scope.

Indexing stays local. Retrieved passages are included in the current user turn and are sent to the selected model, including a cloud model if chosen. Retrieved documents are marked untrusted source material. Source chips remain available independently of whether the model follows citation instructions.

## Artifacts, memory and provenance

Artifacts & Deliverables discovers recent nested output files and opens previews in the app. Chat artifact references resolve only to uniquely identified allowed output files. Arbitrary external paths do not become preview permissions. DOCX and XLSX offer text previews; existing PDF, image and presentation viewers remain available.

Runtime → Personal Memory stores an explicit preferred name and instructions. Sharing between local profiles is opt-in; this is local sharing, not cloud synchronization. Documents, secrets and arbitrary conversation contents are not copied into this identity automatically.

Audit records selected session, tool and inference events in a SHA-256 linked ledger, signed with Ed25519. Records contain bounded metadata and payload hashes rather than raw prompts or API keys. Auxiliary routing records a selection; it does not prove that request completed. Local gateway receipts identify the physical models used. This is a best-effort audit observer, not an exhaustive execution attestation or immutable storage.

Export a checkpoint and retain it outside the workstation to detect removal of the recorded tail or owner-level rewriting relative to that checkpoint. Verify against the ledger with `python scripts/verify_audit_checkpoint.py --help`. A local chain alone cannot detect all history deletion. The Models page can show local token/cost estimates explicitly; those estimates are not a provider invoice.

## Verification record

The required product suite ran 241 tests successfully, with two skips, plus compilation, extension validation, JavaScript syntax and the production UI build. The isolated backend suite passed 49 tests, targeted frontend tests passed 18 tests, and all 10 native-renderer checks passed. The real local Qwen probe answered from synthetic offline knowledge and preferred-name memory in 27.65 seconds, including a document source label. It also attached that label to the preferred name, which came from identity rather than the document: citation placement remains a model-quality limitation. Verify claims against the displayed sources.

Reports are under `data/test-results/`, including `workspace-native-acceptance.json` and `workspace-agent-live.json`. Synthetic local-agent probes use temporary documents and identity, not personal files. A passing routing check does not establish guaranteed OCR or citation accuracy. The desktop launcher now remains alive until its owned Electron application exits, avoiding descendant cleanup by managed launch hosts.

Clean-machine installation, independent security assessment, real phone pairing and full microphone-to-speaker acceptance remain separate release checks. Older release documents describe earlier builds; this note describes the workspace additions.
