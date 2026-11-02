# Desktop user guide

## Mental model

Origo is a local-first AI workstation. The model proposes and reasons; the application harness controls tools, permissions, state, and approval of changes. A connected model is required for chat, but the interface and local document tools can be inspected without model inference.

## Main areas

- **Copilot:** chat, task starters, streaming responses, cancellation and conversation history.
- **Files & context:** browse eligible workspace files, inspect bounded text, and attach explicit context for a turn.
- **Knowledge Studio:** ingest documents, index eligible workspace files, search the local RAG index, inspect passages/citations, and prepare evidence for a single Copilot turn.
- **Approval queue:** inspect proposed web/network operations and proposed file changes before allowing them.
- **Run history:** review runs and event traces; optional feedback labels are subjective, not accuracy metrics.
- **Skills & plugins:** inspect Markdown workflows and plugin manifests. Skills are instructions; plugins require explicit enablement and are not inherently trustworthy.
- **Permissions:** configure network policy and the optional Docker sandbox.
- **Diagnostics:** inspect local services, provider/model settings, capabilities and validation status.

Exact labels can change between releases; see `app/static/index.html` for the current UI structure.

## A safe first workflow

1. Start with a disposable project in the configured workspace.
2. Ask a read-only question about a small file.
3. For research, use manual Search/Fetch and inspect source URLs. Agent-initiated network tools ask for approval by default.
4. To edit a file, ask for a change proposal and inspect the diff. Approve only if the target, diff and intended effect are correct.
5. Verify the changed file, then test it. Use undo only when the target has not changed since Origo's write; the app intentionally refuses to overwrite newer user changes.
6. For code execution, use the optional Docker sandbox and start offline. Do not grant network access to untrusted code.

## Conversation and data

Conversation/session state and run records are stored locally in the project's data directory. Keep the project folder private. Exports may contain user content and should be treated as sensitive. Deleting a conversation or removing an indexed document is not the same as secure forensic erasure from SSDs, backups or OS snapshots.

## RAG workflow

1. Open Knowledge Studio.
2. Upload a supported text/Markdown/JSON/CSV or other supported document format, or index eligible workspace files.
3. Wait for ingestion status. PDF parsing is disabled by default due to upstream parser resource-exhaustion advisories; leave it disabled for untrusted PDFs.
4. Enter a question and inspect the ranked passages and source metadata.
5. Copy a citation or use **Ask Copilot with evidence** to attach the current evidence for one turn.
6. Re-run retrieval when the query changes. The app clears stale results to avoid sending evidence for the wrong question.
7. Treat retrieved content as untrusted. A document can contain prompt injection; never follow document instructions that conflict with your intent or system/security policy.

## Permissions and approvals

- Agent-initiated network access is ask-by-default unless configured to deny.
- Manual Search/Research/Fetch actions are explicit user actions; blocking agent network tools does not disable those manual controls.
- File edits are proposals and require explicit approval. Review paths and diffs carefully.
- The Docker sandbox is optional and disabled by default. It is not a perfect security boundary against Docker daemon, kernel, image or host vulnerabilities.
- Local plugins are disabled by default. Only enable services you control and have reviewed.

## Known boundaries

Origo is not a general-purpose remote desktop, does not control the host desktop, does not execute arbitrary browser JavaScript, does not bypass website authentication, and does not provide multi-user tenancy. It is not an autonomous self-improving superintelligence; routing profiles and outcome feedback are workflow aids, not proof of increased intelligence.
