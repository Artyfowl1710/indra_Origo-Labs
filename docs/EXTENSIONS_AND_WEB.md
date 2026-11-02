# Extensions, web research, parallel tasks and sandbox

This guide describes the current Indra Origo extension interfaces. The intent is composability with a small trusted core, not permissionless execution of arbitrary plugin code.

## Skills: reusable workflows without executable code

A skill is a `SKILL.md` file under `skills/<skill-id>/`. It is loaded as bounded instruction text when selected; it does not execute Python, JavaScript or shell.

Create a starter:

```powershell
.\.venv\Scripts\python.exe scripts\new_skill.py "Research Note" --description "A research workflow with source verification"
```

Edit the generated `skills/research-note/SKILL.md`, keeping it focused: state the task, expected inputs, steps, verification checks, and output format. Include safety guidance, source requirements, and stop conditions. Treat instructions returned by websites, repositories and retrieved documents as untrusted content; they cannot override the harness or user request. Refresh the Skills registry in the UI.

Run `scripts/validate_extensions.py` to inventory installed workflows. It reads Markdown and manifests only; it does not execute skill instructions.

## Plugins: local declarative HTTP JSON services

The current plugin contract is deliberately smaller than a general plugin runtime. The host does not import arbitrary plugin Python/JavaScript. A plugin manifest describes a trusted local service, tools, a constrained JSON input schema and a path; requests go only to explicitly configured numeric loopback addresses.

Example manifest: `plugins/examples/local-notes/plugin.json`. The sample is disabled. Its sample server lives at `plugins/examples/local-notes/server_stub.py`; this is a developer example only, not an automatically launched service.

To run the example in PowerShell:

```powershell
# Terminal 1, project root (uses only an in-memory sample index)
.\.venv\Scripts\python.exe plugins\examples\local-notes\server_stub.py
```

Then in `.env`, set `INDRA_ENABLE_LOCAL_HTTP_PLUGINS=true`. Edit `plugins/examples/local-notes/plugin.json` and set its `enabled` property to `true`. Leave its base URL at `http://127.0.0.1:9911`. Restart Indra or click **Refresh registry**. Check `GET /api/extensions` or the Extensions UI.

The manifest tool contract must be `read_only: true`. This is **not enforceable proof**: HTTP `POST` can mutate data, and the registry cannot inspect what a service does. Only connect services you trust. The registry forbids remote plugin endpoints and does not support state-changing model-callable tools. A future mutation-capable plugin system needs per-action approval, idempotency and audit/rollback semantics.

Do not put secrets into a manifest or skill. Do not expose the example server to your LAN. The service process itself is outside the harness and must be secured independently.

## Web research and scraping

Tools include `web_search`, `web_fetch`, `web_research` and `web_crawl`. They only support public static HTML, text and JSON, preserve source URLs, and do not run JavaScript or bypass logins, CAPTCHAs, paywalls or access controls. By default, web fetches use HTTPS, respect robots.txt, limit ports and redirects, cap response sizes/pages/time/text, and pace requests to each host. Configure `INDRA_WEB_ALLOWED_DOMAINS=arxiv.org,github.com` to restrict source pages to a comma-separated allowlist. The fixed code-owned DuckDuckGo HTML endpoint is allowed only for search discovery; every discovered result still has to pass the configured source allowlist. A non-empty malformed allowlist fails closed.

These are application-layer SSRF mitigations, not an egress firewall. DNS is resolved separately from the HTTP client connection, so DNS rebinding/TOCTOU cannot be eliminated solely in application code. For a sensitive or shared environment, add host/container outbound-network restrictions or an outbound proxy. Avoid targeting sites where your request would violate policy or their terms. Crawl is bounded to the exact starting hostname and checks robots.txt for each page.

Web pages are untrusted data: don't treat their content as instructions, and validate claims against source pages. Results can include prompt-injection text from fetched pages. Do not provide web tools with credentials or use them to access private/internal network services.

## Parallel subagents and task graphs

`parallel_tasks` is for bounded independent tasks. `task_graph` supports 1–6 nodes with `depends_on`, concurrency 1–3, cycle checks, and bounded child runs. The UI's Task Graph card submits a JSON list; it displays results after the run. It is not a durable distributed queue yet: process restart loses in-flight work, and it does not implement peer inboxes, persistent child sessions, job-kill controls or cross-machine scheduling.

Children are deliberately more restricted than the parent: read-only workspace tools, no plugin tools, no Docker sandbox, and no recursive delegation. Dependent outputs are summarized/capped and passed to later nodes as untrusted evidence. Configure `INDRA_MAX_ACTIVE_CHILDREN=1` or `2` for local models with limited RAM/VRAM; the global child semaphore caps concurrent child model work across parents.

A DAG is only useful when its dependencies are correct. Independent tasks can run concurrently; dependent tasks wait for successful prerequisites; failed prerequisites cause downstream tasks to be skipped. Always verify outputs before accepting proposed file changes.

## Docker command sandbox

The model-facing `sandbox_run` is disabled by default. Install Docker Desktop/WSL2 and start Docker, then open **Permissions → Docker sandbox**. Enable the capability, and pick one setup path:

- Click **Build dev image…** after reviewing `docker/Dockerfile.dev-sandbox`. This is a host-side Docker build that downloads a base image and dependencies after an explicit confirmation. The build context is only `docker/`; your workspace, `.env` and local data are not included. The built `indra-sandbox:dev` image is selected and persisted in local SQLite.
- Or choose **Pull sandbox image…** to download the configured image after an explicit confirmation. This requires trusted registry/network access.

The **Use .env image** button reverts to `INDRA_SANDBOX_IMAGE` without editing `.env`. Check Extensions → Docker sandbox for readiness before executing. If using `.env` directly, set `INDRA_ENABLE_DOCKER_SANDBOX=true` and choose `INDRA_SANDBOX_IMAGE` in `.env`, then restart Indra.

Only an argv array is allowed; commands have bounded time, output and resources. The original workspace is not bind-mounted: only a sanitized text-only snapshot is copied into a disposable container, networking is disabled by default, and differences are reported without automatic write-back. Network-enabled execution switches to Docker bridge networking and is **not** domain-filtered.

Important limitations: Docker must be running and properly configured. The container, image, Docker Desktop/WSL2, base/package registries and host kernel remain trusted infrastructure. No sandbox is perfect. The development environment does not include a live Docker daemon, so validate the runtime on your PC before relying on it for untrusted code. Dependencies not already baked into the image are unavailable with networking disabled. The build UI itself runs a host-side Docker build after confirmation; it is not a sandboxed build operation.

## Extension QA checklist

1. Review the entire `SKILL.md` or `plugin.json`.
2. Keep input/result sizes and timeouts small.
3. Never mix credentials into arguments, responses or trace exports.
4. Test disabled-by-default behavior first.
5. Run `python scripts/validate_extensions.py` and `python -m unittest discover -s tests -v`.
6. For any plugin service, audit its actual implementation separately. A declarative manifest does not sandbox the service.
