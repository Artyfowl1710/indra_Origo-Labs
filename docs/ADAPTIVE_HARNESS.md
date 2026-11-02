# Adaptive harness: design and evaluation boundaries

## Control-plane principle

The model proposes. The harness enforces permissions, budgets and state transitions. The evaluator measures outcomes. The model cannot raise its own hard ceilings or approve its own writes.

## Current adaptive behavior

`app/harness.py` classifies task text into one of three deterministic profiles:

| Profile | Step cap | Tool-call cap | Time cap |
|---|---:|---:|---:|
| Fast | 3 | 5 | 45 s |
| Balanced | 8 | 16 | 120 s |
| Deep | 14 | 32 | 240 s |

The `.env` settings `INDRA_MAX_STEPS`, `INDRA_MAX_TOOL_CALLS` and `INDRA_MAX_RUN_SECONDS` are hard ceilings and can only lower profile budgets. `INDRA_PROFILE=auto` enables task-text heuristics; set `fast`, `balanced` or `deep` to override. Selected profile and budget are stored with the run.

These routing signals are transparent keyword/length heuristics. They are not a trained policy, LLM judge or evidence of improved task success. `scripts/harness_eval.py` is a five-case deterministic routing regression smoke test only.

## Context and optional retrieval

`build_context_pack` ranks common project entry points and path matches, then includes readable text files until the configured character budget is reached. It excludes `.env*`, known credential files/directories, binary/unrecognized extensions, oversized files, symlinks and common dependency/build directories. Every path in the context pack is visible in the preview. Project data is untrusted context, not instructions.

Optional `search_knowledge_base` is exposed to the agent only when `QDRANT_COLLECTION` and `EMBEDDING_MODEL` are configured. It sends a query to the configured OpenAI-compatible `/embeddings` endpoint, then asks Qdrant for points in that one collection using the read-only query endpoint. It does not index, upsert, delete or change collection settings. The endpoint must use the same embedding model and vector dimensions as the stored points. Returned payload fields and text are bounded; retrieved text remains untrusted evidence.

## Streaming and observability

`POST /api/chat/stream` sends incremental output and lifecycle/tool events via SSE. The provider reconstructs tool-call deltas before execution, and attempts a standard chat completion if an endpoint rejects streaming. Streaming improves perceived latency; it does not make inference itself faster. Local traces contain user prompts, tool arguments and bounded tool excerpts; treat `data/` and research exports as sensitive.

The model smoke test performs one user-triggered inference request with a synthetic function schema. It inspects the response but never executes the probe or a real tool. A partial result means text generation worked but function calling was not observed.

## Evaluation and future adaptation

Before calling an adaptive policy an improvement, compare baseline/candidate on the same fixed tasks, executor/model configuration, budgets and seed where applicable. Use held-out tasks and repeated trials when model output is stochastic. Report task success, safety violations, tool errors, latency/cost, confidence intervals and failures. Version all candidates and allow rollback. The optimizer must not change approval requirements, workspace boundaries, credential handling, or network exposure.


## Explicit context attachment

The context builder creates a bounded, secret-filtered workspace snapshot and lists the files included. It is not automatically sent to the model: the user must choose **Use in next chat**. At most 12,000 characters are attached to one turn; the run records the attachment flag and character count, but conversation history does not duplicate the raw workspace snapshot. This explicit opt-in trades a larger prompt for relevant repository evidence and avoids silently increasing latency or sending additional files to hosted endpoints.


## Composable extension boundary

The extension design borrows the broad idea of capability seams—skills, tools/plugins and child agents—from emerging open-source agent harnesses. DeepSeek Harness publicly describes an “everything is a plugin” architecture, composable capabilities and agent-team/subagent features; Indra deliberately implements a narrower trust model rather than copying that runtime. See the [DeepSeek Harness overview](https://www.deepseek.com/en/harness/) and [capability-seams documentation](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/capability-seams.md).

Indra's current integration contract is intentionally limited: Markdown skills are non-executable; plugins are declarative and loopback-only; child agents get a read-only tool set and cannot invoke plugins, run commands or recurse; command execution requires an explicit Docker sandbox. This lowers the number of trusted host components, but does not make a configured plugin service or Docker daemon inherently safe.
