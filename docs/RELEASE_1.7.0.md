# Indra Origo 1.7.0 — Knowledge Studio + hybrid retrieval

## What changed

- Added first-party local RAG storage using SQLite, WAL mode, and FTS5 BM25; Qdrant is not required.
- Added bounded file ingestion for UTF-8 text, common source-code/config formats, structured text, and digitally text-extractable PDFs. Ingestion enforces a 7 MiB source-file ceiling, bounded character/chunk counts, chunk overlap, filename/path secret exclusions, and common credential redaction.
- Added optional OpenAI-compatible dense embeddings, fused with lexical ranking using weighted reciprocal-rank fusion and then scored with an evidence-oriented reranker (term coverage, phrase match, filename match, vector similarity). Duplicate-like passages are suppressed and adjacent chunks can be included as context without changing the matched chunk's citation.
- Embeddings are an **explicit opt-in** through `RAG_EMBEDDING_MODEL`, `RAG_EMBEDDING_BASE_URL`, and `RAG_EMBEDDING_API_KEY`. The app does not infer an embedding model from the older Qdrant `EMBEDDING_MODEL` variable. When configured, chunks and queries are sent to that endpoint. The endpoint host and privacy note are displayed in Knowledge Studio.
- A SHA-256 signature of endpoint + embedding-model identity is stored with indexed vectors. Search only compares vectors that share the active signature, avoiding accidental cross-space similarity when an embedding model or endpoint changes. Re-index documents to refresh vectors after changing providers.
- Added Knowledge Studio for upload, read-only selected-workspace indexing, retrieval inspection, local library management, citation copying, and a one-turn evidence attachment to Copilot.
- Added a read-only `search_rag` agent tool that uses the same cached index as the HTTP API. Retrieved passages are explicitly treated as untrusted evidence rather than instructions.
- Extended common token redaction, corrected external-embedding privacy disclosure, added command-palette access, kept all workspace buttons visible as icon navigation on mobile, and moved one-turn prepared context into ephemeral centralized UI state. Per-resource epochs prevent stale retrieval responses overwriting newer results; query edits invalidate old evidence handoff, and document-library filters narrow by filename/path and source type.

## Data, privacy, and safety boundaries

- The library database is `data/rag.sqlite3` (under `INDRA_DATA_DIR`). Original workspace files are not modified by indexing; deleting a library entry deletes only the index record.
- With no `RAG_EMBEDDING_MODEL`, retrieval is local SQLite/FTS5 only and no embedding requests are sent.
- With semantic retrieval enabled, text from selected chunks and the query are sent to the configured embedding endpoint. Configure a local endpoint for local-only processing; do not assume a configured endpoint is local.
- The common-token scrubber is best-effort defense in depth, not a complete secret scanner. Avoid deliberately importing credential files; sensitive filenames and directories are blocked and workspace indexing rechecks path and file filters.
- PDFs must contain extractable text; scanned/image-only PDF OCR is not implemented. Semantic embedding is capped at 256 chunks per source document; excess chunks still receive lexical indexing.
- `[R1]`, `[R2]`, etc. are labels scoped to the current retrieval result/context pack. The underlying document and chunk IDs are stable local identifiers. Retrieval confidence is a heuristic, not a calibrated probability or guarantee of factual correctness.
- The app is intended for a single trusted user on loopback, not for public/LAN exposure.

## Verification

Run from the project root:

```powershell
python -m compileall -q app scripts tests
python -m unittest discover -s tests -v
python scripts/validate_extensions.py
node --check app/static/app.js
```

Validation performed on 2026-10-29: 183 Python unit tests passed; Python compilation, JavaScript syntax and extension validation passed; the static HMI quality gate passed 24/24 checks with no warnings. Static-source HMI checks are not a substitute for real-browser, screen-reader, or moderated usability tests. Unit-test success does not imply a full human usability study, security certification, or model-quality benchmark.
