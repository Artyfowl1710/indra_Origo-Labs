# Troubleshooting (Windows)

## The browser does not open

1. Run `start_indra.bat` again. The launcher reuses a managed instance if it is healthy, otherwise it chooses a free port from 8765–8775.
2. Check `logs\server-error.log` and `logs\server-out.log`.
3. Open the URL printed by the launcher. If the port changed, use the printed URL instead of assuming `8765`.
4. Check `http://127.0.0.1:<printed-port>/api/health`. It should return `ok: true`, app `Indra Origo`, and a version.

## Setup or dependency installation failed

- Install Python 3.10+ from python.org and enable the Windows Python Launcher. Run setup from a writable folder.
- First-time `pip install` needs access to the configured package index/proxy. If it fails, fix connectivity and run `setup_windows.ps1` again.
- Setup deliberately stops if compilation or unit/API tests fail. Read the first failing assertion; do not bypass the test gate just to launch a broken build.
- Node.js is optional. If available, setup checks `app\static\app.js` syntax too.

## Model shows disconnected

- Start llama-swap or llama.cpp yourself; this build does not manage those processes.
- Open Diagnostics, verify the endpoint address and advertised model IDs, then select an exact alias or use Auto-detect.
- Set `OPENAI_BASE_URL` to the OpenAI-compatible API root, usually including `/v1`, in `.env`.
- Click **Test inference + tool calls** only after a model has loaded. A passing test confirms a synthetic tool call was returned; it does not validate all tools or guarantee task quality. A partial result means text generation worked but tool calling was not observed.
- Large models can take a while to load and may run slowly on a 6 GB GPU. This does not necessarily mean the harness UI is hung; check the inference server's logs and memory use.

## Qdrant retrieval is disabled or returns an error

- Leave it disabled unless your collection is already indexed and you know the embedding model and dimensions used for those vectors.
- Set `QDRANT_COLLECTION`, `EMBEDDING_MODEL`, and `EMBEDDING_BASE_URL`; set `QDRANT_API_KEY` if your Qdrant requires it.
- The embeddings API must implement `POST /v1/embeddings`. The vector dimensions must match the selected Qdrant collection.
- Retrieval is read-only. It will not create a collection or embed/index your workspace.

## Search cannot find a file

Search covers readable text-like files only, and excludes secrets, symlinks, common dependency/build directories and oversized files. Refresh the inventory after changing the workspace. A path outside the selected workspace is deliberately inaccessible.

## Undo or approval reports a conflict

The file changed after a proposal was created or applied. Indra refuses to overwrite newer content. Read the current file, create a fresh proposal, or restore from a verified backup manually after reviewing it.

## Data locations

- `.env`: local endpoint and limit settings; never share it if it contains real keys.
- `data\indra.sqlite3`: runs, events, settings, approvals and saved conversations.
- `data\backups\`: verified overwrite backups.
- `logs\`: launcher stdout/stderr diagnostics.

Close Indra after saving drafts before copying the project-level `data` directory for reinstall/backup. Do not copy only a live database file while leaving behind its journals; use SQLite's backup API for a live snapshot. Do not put SQLite WAL databases on network shares. If Indra refuses a database journal transition, close other instances and retry; never delete WAL/SHM/journal files as a repair shortcut. See [database runtime safety](DATABASE_RUNTIME_SAFETY.md).


## Web search or scraping is blocked

- With `INDRA_WEB_ALLOWED_DOMAINS` set, fetched source pages must match one of those domains. The fixed DuckDuckGo HTML endpoint is an internal discovery dependency; result URLs are still filtered through your source allowlist.
- A `robots.txt` denial or inaccessible policy may block a page; the fetcher does not bypass it. Remove `INDRA_WEB_ALLOWED_DOMAINS` only if a broad public-web scope is intentional and permitted by your policy.
- Only public static HTML, text and JSON are supported. JavaScript-rendered pages, private/internal IPs, credentials in URLs, custom ports, downloads and auth/CAPTCHA bypass are unsupported.
- DNS/IP checks reduce SSRF risk but are not a firewall. Keep outbound network controls in place for sensitive work.

## A local plugin is missing or not callable

- Check that `INDRA_ENABLE_LOCAL_HTTP_PLUGINS=true` is set in `.env` and that the specific manifest has `"enabled": true`.
- Ensure the base URL is a numeric loopback address with an explicit port, the endpoint path is valid, and each tool uses a restricted object schema with `additionalProperties: false` and `read_only: true`.
- Start the service yourself in a separate terminal, then restart Indra or use **Refresh registry**. Indra never auto-starts a plugin service.
- Run `scripts/validate_extensions.py`. It validates manifests but does not contact plugins. Use the plugin's `/health` endpoint or inspect its own logs if the service is unreachable.
- The `read_only` manifest field is a trust assertion, not a guarantee. Use only a service whose implementation you have reviewed.

## Parallel tasks appear slow or fail

- Check model availability and active run limits in Diagnostics. Parallel children issue real model requests and may compete for RAM/VRAM; use `INDRA_MAX_ACTIVE_CHILDREN=1` on a constrained workstation.
- Keep independent tasks small, specify real `depends_on` IDs for DAG nodes, and avoid sending huge context to every child. Cyclic/unknown dependencies are rejected before model calls.
- Child agents are intentionally read-only and cannot call plugins, run Docker commands, write files or create more child agents. A failed prerequisite causes dependent nodes to be skipped.

## Docker sandbox is not ready

- Install and start Docker Desktop/WSL2, then pull the configured image manually (the default is `docker pull python:3.12-slim`). Indra does not download images implicitly.
- Set `INDRA_ENABLE_DOCKER_SANDBOX=true` only after reviewing the command/tool policy. Confirm the image is Linux-based and includes `/bin/sh`, `sleep` and `chmod`.
- The sandbox has no network, so it cannot install packages during a run. If dependencies are required, build and review a custom local image before configuring it.
- If Docker is unavailable, command execution stays disabled. Indra never falls back to the host shell.
