# Configuration reference

Configuration is read from `.env` in the project root. `.env.example` is the canonical inventory. Restart Origo after changing values. Never commit `.env` or paste tokens into issues/screenshots.

## OpenRouter test profile

To try Dots3-Note Preview, add these values to your private `.env`, restart Origo, and select **Hosted compatible endpoint** in Diagnostics:

```env
INDRA_HOSTED_BASE_URL=https://openrouter.ai/api/v1
INDRA_HOSTED_API_KEY=<your key>
INDRA_HOSTED_MODEL=dots-studio/dots-3-note-preview:free
```

The hosted profile sends chat prompts, attachments, selected workspace context, and tool results to OpenRouter and its serving provider. Keep the local profile selected for private inference. Preview free endpoints may change or disappear; verify availability in Diagnostics. Origo's smoke check tests inference and synthetic tool-call format; it does not grant tool permissions. Never commit the key.

| Variable | Purpose | Safe baseline |
|---|---|---|
| `OPENAI_BASE_URL` | OpenAI-compatible chat endpoint | `http://127.0.0.1:8100/v1` |
| `OPENAI_API_KEY` | Provider credential/token | Local dummy value only if gateway does not require auth; otherwise use secret |
| `MODEL` | Model ID or `auto` | `auto`, then verify in Diagnostics |
| `INDRA_REQUEST_TIMEOUT` / `INDRA_CONNECT_TIMEOUT` | Provider timeout controls | Keep bounded |
| `INDRA_WORKSPACE` | Workspace root | `./workspace` |
| `INDRA_DATA_DIR` | SQLite/state directory | `./data` |
| `INDRA_BACKUP_DIR` | Approved-edit backups | `./data/backups` |
| `INDRA_AGENT_NETWORK_POLICY` | Agent web tools policy | `ask` or `deny` |
| `INDRA_WEB_TOOLS_ENABLED` | Enable public web tools | `true` only if needed |
| `INDRA_WEB_ALLOWED_DOMAINS` | Optional comma-separated hostname allowlist | Set for constrained research |
| `INDRA_WEB_ALLOW_HTTP` | Permit HTTP web requests | `false` |
| `INDRA_ENABLE_LOCAL_HTTP_PLUGINS` | Enable loopback HTTP plugin services | `false` |
| `INDRA_PARALLEL_SUBTASKS` | Child-agent concurrency | `1`–`2` on local GPUs |
| `INDRA_MAX_ACTIVE_CHILDREN` | Cross-request child cap | `1`–`2` |
| `INDRA_ENABLE_DOCKER_SANDBOX` | Enable sandbox capability | `false` until configured |
| `INDRA_SANDBOX_IMAGE` | Container image | Review image source before use |
| `INDRA_SANDBOX_MEMORY_MB`, `INDRA_SANDBOX_CPUS`, `INDRA_SANDBOX_PIDS`, `INDRA_SANDBOX_WORKSPACE_TMPFS_MB` | Sandbox resource bounds | Defaults in `.env.example`; hard ceilings apply |
| `QDRANT_URL`, `QDRANT_COLLECTION`, `QDRANT_API_KEY` | Optional read-only Qdrant search | Leave collection empty if unused |
| `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL` | Embedding endpoint for optional Qdrant retrieval | Must match indexed vectors exactly |
| `RAG_EMBEDDING_BASE_URL`, `RAG_EMBEDDING_API_KEY`, `RAG_EMBEDDING_MODEL` | Separate optional embedding endpoint for first-party RAG | Leave model empty for local lexical-only retrieval |
| `INDRA_REMOTE_ACCESS_ENABLED` | Explicit remote access opt-in | `false` |
| `INDRA_REMOTE_ACCESS_TOKEN` | Remote login secret | Generate with setup script; never commit or share |
| `INDRA_ALLOW_UNSANDBOXED_PDF` | Permit in-process PDF parsing | `false`; only trusted PDFs if explicitly enabled |

### Secrets and rotations

- Treat API keys, remote tokens, SQLite databases, conversation history, logs, exports and backups as private.
- If a remote token is exposed, generate a new token and restart Origo; this invalidates previously signed cookies.
- If a provider key is exposed, revoke it at the provider and update `.env`.
- Avoid putting secrets in command-line arguments, shell history, screenshots or crash reports.
- Environment variables can override local assumptions; review the actual process environment when diagnosing unexpected behavior.

### Local versus hosted inference

A localhost endpoint is intended for local inference. A hosted endpoint can receive prompts, tool outputs and RAG evidence. Never assume retrieval stays local merely because documents are stored locally; an external embedding endpoint receives chunk/query text when configured.
