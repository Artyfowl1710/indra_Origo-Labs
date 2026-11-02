# Knowledge source review and freshness

Indra's native Knowledge screen now distinguishes source versions and review state. Open **Knowledge → Review source details** on a document. Preview its stored passages, verify the source, and save its document family, version, owner, effective date, review due date and review status.

Header extraction recognises scalar `Document:`, `Title:`, `Version:`, `Owner:`, `Effective date:` and `Review due:` lines in the first 4,000 characters/50 lines. Dates use `YYYY-MM-DD` and UTC. Extracted details are suggestions: an uploaded document cannot declare itself approved. Existing collections migrate to **unreviewed** without losing their content.

## Current and superseded sources

Mark a document **Reviewed current** only after inspecting it. To replace an older policy, review the replacement first, then set the older document to **Superseded** and choose the current replacement from the same document family and collection. Review changes use the last observed content/metadata revision; stale requests cannot overwrite newer edits.

Superseded and future-effective documents are excluded before candidate limits in lexical, semantic and fallback retrieval, and again when passages are assembled. They remain visible in the library. Deleting a replacement does not resurrect the old source. Quarantined documents cannot be approved or used as replacements.

Changing a reviewed document's content clears its current approval. Reindexing unchanged content retains approval. Reindexing a superseded document keeps it superseded until an explicit review changes that decision.

Returned citations and model context carry version, review status, owner and warnings. Unreviewed or overdue documents remain retrievable with warnings; they are not silently treated as authoritative. Marking a document current records a user's review, not an independent certification of its truth or owner identity. Existing chat history cannot be retracted when a source changes.

## Potential conflicts and local owner digest

The source-review panel lists overdue/unreviewed documents, duplicates, related versions and potential numeric disagreements between related or similar first passages. It compares up to 200 non-quarantined documents and 400 notices; the panel reports when that scope is bounded. Source text and declared metadata remain untrusted data.

This is a deterministic offline heuristic, not a semantic contradiction detector. It can miss disagreements later in a file, negation, changed words or multilingual number words, and may flag unrelated numeric changes. Same-family grouping is a review aid. Potential conflicts affecting retrieved sources are included in answer context with a warning to request human review. Explicitly superseding the old source resolves that retrieval conflict.

Export the local review digest to share through your own process. Indra does not send messages to owners. Owner reminders/scheduling, deep semantic conflict analysis and full historical version storage remain open. Reingesting a filename/source replaces that indexed copy; preserve distinct source files if both versions must remain inspectable.

Stored-source preview returns at most 16,000 characters from 20 passages, with possible chunk overlap and a truncation warning. It renders plain text, including quarantined text, without executing HTML or sending it to a model. It is a bounded inspection aid, not a complete document viewer.

## Verification

Passed 307 product tests (two skips), 47 focused backend tests, 33 frontend tests, 42 isolated desktop checks, build and required validation. Tests cover migration, stale concurrent reviews, updated-content invalidation, supersession across all retrieval channels, future dates, quarantine, profile/collection boundaries, source preview, signed Audit and existing voice/folder/memory flows. The original SIH reference folder is unchanged. The main desktop was not restarted; the new backend and UI load together on the next normal launch.

The real local Qwen 3.5 4B fixture answered with the approved name, imported programming preference and **12-month current policy**, cited its source and warned it was overdue. The superseded six-month passage was absent. Agent time was 12.24 seconds. This is one synthetic model acceptance case.

Run the reproducible offline retrieval fixture:

```powershell
.\.indra-python\Scripts\python.exe scripts\benchmark_offline_knowledge.py
```

On this machine, 13 synthetic documents and nine English queries (three repetitions each) produced recall@3 **1.0**, reciprocal rank **1.0**, precision@3 **0.3704**, median query time **18.63 ms**, and a maximum context of **858 characters**. The fixture refused all socket connections, used the resident offline MiniLM encoder, and excluded retired, future and poisoned sources. Low precision reflects returning three passages when most questions have one labelled relevant source. These results do not establish large-library, multilingual or general answer quality; character counts are not model token counts.

Local evidence is under `data/test-results/knowledge-lifecycle-*`, `knowledge-freshness-agent-live.json` and `offline-knowledge-benchmark.json`. Broader acceptance remains in [the product ledger](PRODUCT_GOAL_ACCEPTANCE.md).
