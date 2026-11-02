# Personal setup and reviewed memory

Indra can remember your preferred name, interests, working preferences and up to 20 reviewed personal facts. Open **Runtime → Make Indra yours** to edit them. New, empty profiles also show an optional first-use setup dialog. Existing populated profiles keep their current flow.

New profiles default to keeping personal context out of model requests. Select **Include this personal context in future model requests** to enable it. This includes cloud models when selected. Turning it off keeps the saved details on disk but removes this feature's personal context from future requests. It cannot retract previous messages or remove information already present in a conversation. Legacy manually saved profiles retain their prior request behaviour during migration.

Personal context is attached to the current request. Changing it does not rewrite old chat messages or mutate the conversation's cached system prompt. Personal facts never grant tools, folder access or approval permissions.

## Import from another assistant

1. Export or copy that assistant's saved memories into a UTF-8 text file, one fact per line, or a JSON list. Full conversation exports are deliberately unsupported.
2. Save any pending edits in Indra, then choose **Review a memory export**.
3. Select the facts you want and choose **Import selected**. Nothing is selected automatically.

Accepted JSON examples:

```json
{"memories": ["I prefer practical examples.", {"content": "My project language is Python."}]}
```

The importer accepts at most 128 KiB, 100 candidates and 400 characters per fact. Your profile holds at most 20 facts. It parses locally without an LLM or external API. Likely credentials are hidden and blocked; suspicious instructions are quarantined. These are bounded heuristics, not a trained classifier or a guarantee: review the text yourself. Uploaded file names never become file paths to read.

Previews are profile-bound, expire after 15 minutes and can be committed once. Changed personal context invalidates an older review. Expired stored previews are pruned when another preview is created; they are not automatically erased at the expiry timestamp. Pending reviews are limited to eight per profile. Signed Audit records hashes and counts rather than memory text. No chat content is automatically harvested into this personal-memory store.

Use **Remove** and then **Save personal memory** to delete a saved fact. **Export reviewed memories** downloads just the reviewed facts as JSON, not your name or working preferences. Import does not enable request consent or cross-profile sharing.

## Local profile sync

Sharing is off by default. Only profiles that explicitly opt in read the shared name, interests, working preferences and reviewed facts. Request consent and first-use completion remain local to each profile. This is synchronization between opted-in profiles on this PC, not cloud-account or cross-device sync. Turning sharing off stops that profile from reading subsequent updates; it does not delete details already shared to other profiles or the shared file.

Updates use a shared file lock, an atomic file replacement and a local SQLite transaction, with compensation if that transaction fails. A power loss between the file update and database commit can still leave these two stores out of step; this is not a distributed transaction. Storage remains readable to the operating-system account. Do not store secrets here.

## Verification and limits

Current checks passed: 296 product tests (two skips), 48 focused backend tests, 32 frontend tests, production build and 35 isolated native renderer checks. The renderer covers setup, opt-in consent, saved navigation, explicit selection, quarantined imports, persisted retrieval, and narrow layout alongside existing voice/folder checks. Synthetic data only; no actual microphone or cloud inference is used by that renderer fixture.

A real signed local Qwen 3.5 4B process answered the synthetic preferred-name, imported-language and document-maintenance question correctly, including the source citation, in 9.15 seconds of agent time. The earlier attempt through the prior desktop gateway failed because that port was no longer listening; the isolated owned model process passed and was stopped afterward. This is one bounded acceptance fixture, not a general memory-quality benchmark.

The user's main app was not restarted for this change. The new backend routes and rebuilt UI load together on the next normal app launch. Cloud/cross-device memory sync, arbitrary vendor conversation archives and automatic memory extraction remain outside this implemented flow. Broader product requirements remain tracked in [the acceptance ledger](PRODUCT_GOAL_ACCEPTANCE.md).
