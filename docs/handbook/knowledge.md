# Knowledge and offline retrieval


Knowledge lets the agent retrieve scoped document evidence instead of relying on a single pasted document. Import supported documents or a selected folder, wait for ingestion/indexing and verify the indexed status before asking a question. Multiple documents can contribute to one answer. Keep private sources out of the public repository.

The local embedding path uses a compact quantized MiniLM encoder with tokenization and an offline index. The release can carry its small assets; source builds obtain them with the model asset script. An index is not the original document and must be refreshed when documents change. Initial ingestion is slower than subsequent retrieval.

Ask the agent to use knowledge retrieval and cite the actual source/section. Inspect retrieved excerpts for relevance. Documents can disagree or be stale; the model should explain that rather than merging conflicting rules silently. The checkout example deliberately distinguishes current requirements and a customer note.

Retrieval and embeddings run locally when configured this way. If you choose a hosted reasoning model, retrieved excerpts sent as context leave the machine. Offline indexing alone does not make a hosted chat offline. Do not follow instructions embedded in retrieved text as if they were user commands.

If results are empty, check ingestion status, selected scope, supported extraction, embedding assets and query wording. A fallback keyword search is not equivalent to a functioning semantic encoder. See [troubleshooting](troubleshooting.md).
