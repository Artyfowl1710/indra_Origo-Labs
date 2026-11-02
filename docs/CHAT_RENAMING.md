# Model-callable current-chat names

Indra's agent can now call **`rename_current_chat`** when a conversation's focus becomes clear or when you ask it to choose a name. For example: “Name this chat Release readiness.” The model decides whether to invoke the tool; the tool reports the name actually saved. The existing manual `/title Your name` command remains available.

The product-owned tool extends the existing file toolset and also works through the harness's normal deferred-tool bridge. It does not add a second title store or a separate RPC service. New agents load its schema normally; it does not change a running conversation's cached tool definitions or system prompt.

## Scope and safeguards

- The tool accepts only a title, up to 80 characters. The harness supplies the active durable session identity. Model arguments cannot choose another chat, profile or database path.
- Titles are sanitized using the existing session-title rules. Obvious instruction/credential strings are rejected. This is not complete secret detection; do not put private information in chat names.
- Duplicate names receive a suffix such as `#2`. The conflicting chat and compressed ancestors keep their names.
- A model can refine an earlier model-generated title. Replacing a user-chosen title requires fresh human approval. Denial keeps the old name. The original manual-title authority remains after an approved replacement.
- Checked writes compare the title and its source with the values seen before review. A concurrent rename is retained instead of being overwritten. The canonical hidden Bot Chat cannot be renamed.
- Existing content-trust policy still applies. After untrusted document/tool context, a rename requires that turn's fresh human review; YOLO and cached approval do not bypass it. A protected user-chosen title can require a separate replacement review.

Only local title metadata changes. This tool does not rewrite messages, prompt snapshots or project files, and does not rename a Discord channel, WhatsApp conversation or another external service.

## Live updates and Audit

The normal scoped title event refreshes the native chat list. A completed-turn refresh also handles a newly created chat that was below the sidebar's message threshold when its name first changed. Reopening reads the persisted name. The sidebar refresh does not reconnect or replace the active conversation.

Signed Audit records the operation's session, requested/candidate title hashes and completion receipt without storing the title text. The receipt's `human_approved` field refers to approval of a protected user-title replacement; content-trust reviews are recorded separately. If the intent cannot be recorded, the rename stops. A completion-receipt failure after the title write returns an explicit saved-but-unconfirmed warning. The two databases are not one atomic transaction; a crash can leave an intent without a receipt.

The core now has an additive checked-title operation, while existing manual and automatic title setters keep their precedence rules. Tool delivery remains an installed-product plugin capability, rather than a permanent new core tool. CLI/headless calls can persist names without a live UI event sink. Native Google Live voice's restricted tool set is separate; this change is verified for the coding/agent harness.

## Verification

Passed 307 product tests (two skips), 57 focused backend tests, 27 frontend tests, production build, required validation and 52 isolated native checks. Tests cover current-profile scope, duplicate names, user-title approval/denial, concurrent edits, canonical names, unchanged transcript/prompt snapshots, Audit failure reporting and mandatory review after untrusted context.

An actual local Qwen 3.5 4B model invoked the tool through the standard `tool_call` bridge, received **Dockyard Plan #2**, reported that exact title, kept the other chat's **Dockyard Plan** name and produced a valid signed Audit chain. Agent time was 12.5 seconds. This is one synthetic tool-choice acceptance case, not a general behavior guarantee.

The native fixture uses a deterministic loopback model provider to exercise normal prompt → model tool → SQLite → title event → sidebar paths. It verifies API persistence and reopening, then independently retains voice-only recording/export, folder, memory, Knowledge and usage checks. Its workspace is an empty temporary host folder, so fixture execution does not inherit the source checkout as project context. No cloud credential or real microphone is used. The main user session was not restarted, and the SIH reference folder was not changed.

Evidence is under `data/test-results/chat-title-*` and the native acceptance JSON. The rebuilt backend/plugin and UI load together on the next normal app launch. Overall product acceptance remains in [the complete ledger](PRODUCT_GOAL_ACCEPTANCE.md).
