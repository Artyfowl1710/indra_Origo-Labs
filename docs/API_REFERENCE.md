# API reference (v1.7.2)

The application exposes an HTTP API from FastAPI. This is a practical route inventory, not a frozen OpenAPI contract. For exact schemas, start Origo locally and inspect `/docs` or `/openapi.json`; do not expose those endpoints to untrusted networks. Remote routes are subject to the host/token/session gate.

## Health and configuration

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | App liveness/version |
| `GET` | `/api/status` | Runtime status |
| `GET` | `/api/capabilities` | Feature/capability inventory |
| `GET` | `/api/providers` | Provider profiles |
| `POST` | `/api/provider/profile` | Select provider profile |
| `GET` | `/api/settings` | Current settings view |
| `GET` | `/api/policy` | Read policy |
| `POST` | `/api/policy` | Update policy |
| `GET` | `/api/doctor` | Diagnostic checks |
| `GET` | `/api/models` | Models advertised by configured gateway |
| `POST` | `/api/model` | Select model |
| `POST` | `/api/model/smoke` | Explicit inference/tool smoke test |

## Sessions and state

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/scratchpad` | Read scratchpad |
| `PUT` | `/api/scratchpad` | Update scratchpad |
| `GET` | `/api/sessions` | List sessions |
| `POST` | `/api/sessions` | Create session |
| `GET` | `/api/sessions/{conversation_id}` | Read session |
| `PATCH` | `/api/sessions/{conversation_id}` | Rename session |
| `DELETE` | `/api/sessions/{conversation_id}` | Delete session |
| `GET` | `/api/export` | Export selected application data |

## Permissions, workspace and sandbox

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/permissions/pending` | List pending permission decisions |
| `POST` | `/api/permissions/{permission_id}` | Approve/deny a pending action |
| `POST` | `/api/workspace/select` | Select workspace root |
| `GET` | `/api/sandbox/status` | Sandbox readiness/status |
| `POST` | `/api/sandbox/build-image` | Explicitly requested development image build |
| `POST` | `/api/sandbox/pull-image` | Explicitly requested image pull |
| `GET` | `/api/extensions` | Extension/skill status |
| `POST` | `/api/extensions/reload` | Reload extension inventory |
| `GET` | `/api/skills/{skill_id}` | Read skill details |

## Knowledge Studio / RAG

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/rag/status` | RAG readiness and configuration status |
| `GET` | `/api/rag/documents?limit=200` | List indexed documents; limit 1–500 |
| `POST` | `/api/rag/ingest` | Ingest a supported document payload |
| `POST` | `/api/rag/index-workspace` | Index eligible workspace files |
| `POST` | `/api/rag/search` | Search and retrieve evidence passages |
| `POST` | `/api/rag/ask-context` | Prepare current evidence for a Copilot turn |
| `DELETE` | `/api/rag/documents/{doc_id}` | Remove indexed document/chunks from the RAG index |
| `GET` | `/api/knowledge/status` | Knowledge subsystem status |

PDF parsing is disabled by default. Do not set `INDRA_ALLOW_UNSANDBOXED_PDF=true` for untrusted PDFs. External embedding configuration transmits document chunks and queries to that endpoint.

## Web research

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/web/search` | Explicit search action |
| `POST` | `/api/web/fetch` | Fetch a public URL under policy constraints |
| `POST` | `/api/web/research` | Multi-step bounded research workflow |

Agent-initiated network actions are approval-gated by default. Public URL validation does not fully eliminate DNS rebinding/SSRF risk. Do not use this API as an unrestricted proxy.

## Remote session

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/remote/login` | Remote token sign-in page when remote gate applies |
| `POST` | `/remote/login` | Submit remote access token; request body is size-capped |
| `GET` | `/remote/logout` | Clear current remote session cookie |

The remote login mechanism is a single-user personal access boundary, not multi-user SSO. Keep tailnet ACLs restrictive and never port-forward the app.

## Chat, runs, actions and evidence

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/chat` | Non-streaming chat run |
| `POST` | `/api/chat/stream` | Streaming chat events |
| `POST` | `/api/task-graph` | Explicit bounded read-only task graph |
| `GET` | `/api/runs` | Run history |
| `GET` | `/api/metrics` | Local run metrics/summary |
| `GET` | `/api/feedback` | Optional human feedback labels |
| `POST` | `/api/feedback` | Record/update subjective feedback |
| `DELETE` | `/api/feedback/{run_id}` | Remove feedback for a run |
| `DELETE` | `/api/feedback` | Clear feedback records |
| `GET` | `/api/actions` | List proposed/pending actions |
| `POST` | `/api/actions/{aid}` | Resolve/apply an action according to its state and policy |
| `POST` | `/api/actions/{aid}/undo` | Attempt guarded undo |
| `GET` | `/api/context` | Current bounded context view |
| `GET` | `/api/workspace` | Workspace inventory |
| `GET` | `/api/workspace/search` | Search eligible workspace files |
| `GET` | `/api/workspace/read` | Read eligible text content |
| `GET` | `/api/git/status` | Local Git status helper |
| `GET` | `/api/hmi/audit` | Static HMI audit results |
| `GET` | `/api/capsules` | List Origo Capsules |
| `POST` | `/api/capsules` | Create selected-file Capsule |
| `POST` | `/api/capsules/{capsule_id}/verify` | Verify Capsule signature and file hashes |
| `GET` | `/api/capsules/{capsule_id}/receipt` | Read verification receipt |
| `GET` | `/api/capsules/{capsule_id}/download` | Download Capsule archive |
| `GET` | `/api/proof/ledger` | Read Proof Ledger |
| `POST` | `/api/proof/evidence` | Register an evidence excerpt |
| `POST` | `/api/proof/claims` | Register a claim |
| `POST` | `/api/proof/claims/{claim_id}/review` | Record human review state |
| `POST` | `/api/proof/lint` | Lint claim/evidence consistency |
| `GET` | `/api/scout/status` | Scout status |
| `POST` | `/api/scout/run` | Run bounded scout workflow |
| `GET` | `/api/amplifier/status` | Small-model amplifier status |
| `POST` | `/api/amplifier/plan/validate` | Validate a plan |
| `POST` | `/api/amplifier/context/pack` | Build a bounded context pack |
| `POST` | `/api/amplifier/verify` | Run configured verification |
| `POST` | `/api/amplifier/verify/arithmetic` | Arithmetic check helper |
| `POST` | `/api/amplifier/tokens/estimate` | Estimate token budget |
| `POST` | `/api/amplifier/profile` | Select/inspect amplifier profile |
| `POST` | `/api/sandbox/run` | Run a gated command in the Docker sandbox |
| `POST` | `/api/sandbox/propose-changes` | Turn sandbox output into reviewable proposals |
| `POST` | `/api/web/crawl` | Bounded public-site crawl |

Streaming event payloads are defined by the current frontend and route implementation. Use `/openapi.json` and browser devtools on a trusted local instance to inspect the current contract. Do not assume event names are stable across releases without tests.

## API safety notes

- Bind the server to loopback for local mode.
- Do not publish API docs or endpoints to the public internet.
- Use explicit approval for permissions, file writes, sandbox network escalation and image pulls/builds.
- Keep state/export files private and do not use API responses as public logs without redaction.
# Current native desktop voice API

These routes belong to the copied Indra desktop backend, separate from the earlier v1.7.2 API documented above. All use the existing dashboard authentication and profile scope.

| Route | Contract |
| --- | --- |
| `GET /api/indra/voice/status` | Configured generic voice model options, transport type and quota notice; credentials are never returned. |
| `POST /api/indra/voice/transcribe` | Supported audio data URL, up to 8 MiB decoded, optional named provider/model; returns transcription. Covered payloads pass the outbound policy. |
| `POST /api/indra/voice/turn` | Named voice provider/model, text, bounded history and project ID; returns model text and Knowledge citations. |
| `WS /api/indra/voice/live` | Selected supported `model`, optional `profile`, existing local session token or gated single-use ticket; fixed server-side provider connection. First message is selected-model `setup`; later messages are JSON `realtimeInput`, `clientContent` or `toolResponse`. Every outgoing frame is checked before forwarding. |
| `POST /api/indra/voice/token` | Legacy direct-provider credential endpoint. Returns HTTP 409 while the content guard is enabled; migrated clients use the local WebSocket bridge. |

The Live bridge rejects bad admission before connection (4400 model, 4401 authentication, 4403 boundary). Policy/protocol errors stop the active session with a generic JSON error and close code 1008; timed rotation uses 1012. The renderer receives an opaque `indraSession.id` for local records. Provider secrets, error details and upstream URLs are not reflected. See [Live voice bridge](LIVE_VOICE_BRIDGE.md) for limits and current verification scope.

## Native personal memory API

These routes use the existing dashboard session token and optional `?profile=` scope. They do not belong to the legacy v1.7.2 server.

| Route | Contract |
| --- | --- |
| `GET /api/indra/workspace/identity` | Name, interests, instructions, reviewed facts, local request consent, local sharing/setup flags and effective content revision. |
| `PUT /api/indra/workspace/identity` | Save those fields; pass the last returned `revision` to reject stale edits. `use_in_requests` defaults to false. At most 20 facts, 400 characters each. |
| `POST /api/indra/workspace/identity/import/preview` | Multipart `file`, bounded UTF-8 text or memories-list JSON. Returns opaque preview ID, revision, expiry and candidates with quarantine decisions. Does not activate memories. |
| `POST /api/indra/workspace/identity/import/commit` | JSON `id`, `selected` candidate IDs and reviewed `revision`. Requires 1–20 distinct unblocked candidates; validates profile, expiry, current revision and one-use consumption. Request consent is unchanged. |

Stale/expired/invalid reviews return HTTP 400, oversized uploads 413 and malformed typed input 422. Missing or invalid dashboard authentication is rejected by the existing token check. See [personal setup and memory](PERSONAL_SETUP_AND_MEMORY.md) for privacy, persistence and sync limitations.

## Native Knowledge source review

These routes share dashboard authentication and optional `?profile=` / `project=` scope. Document review changes do not grant access to folders or invoke a model.

| Route | Contract |
| --- | --- |
| `GET /api/indra/workspace/knowledge/review-digest` | Bounded local review notices grouped with owner/source details; no external delivery. |
| `GET /api/indra/workspace/knowledge/{doc}/source` | Inert stored-source text, at most 16,000 characters/20 passages, governance, quarantine decision and truncation notice. |
| `PUT /api/indra/workspace/knowledge/{doc}/review` | `family`, `version`, `owner`, `effective_date`, `review_due`, `status` (`unreviewed`, `current`, `superseded`), `superseded_by` and last returned `revision`. Validates dates, revision, safe replacement, family and collection. |

Knowledge list/search/citation responses include `governance` metadata and warnings. Superseded and future-effective sources are excluded from normal retrieval. Stale/invalid reviews return 400; malformed typed requests return 422. The existing session token protects every route. See [Knowledge freshness](KNOWLEDGE_FRESHNESS.md) for operational limits and evidence.

## Native recorded usage reports

Authenticated `GET /api/analytics/usage` and `GET /api/analytics/models` accept `days=1..365` and the existing optional profile scope. They share reconciled main/auxiliary/residual counters. Both return `totals`, `by_task` and `coverage`; usage also returns daily/model and skill/tool views, while Models adds capability metadata.

Totals include `total_cache_write`, cache-inclusive `total_tokens`, and `unknown_estimated_cost_rows` / `unknown_actual_cost_rows` in addition to existing fields. Numeric cost sums remain compatible; consumers must use coverage and unknown-cost indicators before describing a sum as complete. Coverage explains session-start-date grouping, legacy residuals and missing physical-retry/media usage. These counters are aggregated recorded work, not an immutable event-level invoice. See [recorded usage analytics](RECORDED_USAGE_ANALYTICS.md).

