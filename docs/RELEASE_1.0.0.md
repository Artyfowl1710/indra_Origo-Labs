# Release notes — Indra Lok Meta 1.0.0

## Product hardening

- Made the permission broker thread-safe, bounded pending approval requests, and ensured changing the agent network policy to Block revokes pending web requests.
- Clarified the sandbox network boundary: no-network is the default; an approved networked run uses Docker bridge mode and is not domain-filtered.
- Added a one-time confirmation for manual Search, Research and Fetch operations, displaying the query/hostname/URL before the request leaves the machine.
- Updated the UI to display the resource limits reported by the runtime rather than stale hard-coded RAM/CPU figures.
- Added safe sandbox output review: candidate text edits are converted into normal proposals; no sandbox output is automatically copied into the real workspace. Cached output claims are one-time and workspace-scoped.
- Added customizable hard-bounded Docker memory, CPU, PID and workspace tmpfs budgets.
- Added an optional pre-baked Docker dev-sandbox image with in-app **Build dev image…**, **Pull sandbox image…** and **Use .env image** actions. The image build uses only `docker/` as its build context, not the project workspace or `.env`, and requires a detailed UI confirmation. The selected image override persists in local SQLite and can be reset.
- Updated product/security documentation to distinguish app-level safeguards, Docker isolation and native OS sandboxing, and to document missing commercial-agent capabilities honestly.

## Verification performed in the development environment

- Python compilation and frontend JavaScript syntax check.
- Automated unit/API/security tests, including network-policy revocation, sandbox output claim scope/replay protection, private-target redirect checks, stale writes, backup/undo integrity, graph cycle validation and extension schema validation.
- Clean-extraction test of the release ZIP.
- Local FastAPI/HTTP smoke checks and browser smoke tests where the available Chromium runtime supports them.

- **96 automated tests passed**, including the image-build API confirmation, persistence and reset paths.
- A controlled browser-mock test exercised navigation and the context-attachment workflow without JavaScript errors; the browser runner's navigation to local loopback is blocked by this container environment, so this is not a live-server browser test.
- The Docker build API is tested with mocked Docker subprocesses, including explicit-confirmation checks, the isolated `docker/` build context, and persistent image selection/reset. A real Docker daemon/container execution is not available in this development environment.

These checks do not verify operation on the user's PC, against their local model server, or against a live Docker Desktop daemon.

## Known limitations

- Docker runner is optional and disabled by default. Real container execution must be tested against a running Docker Desktop Linux daemon before relying on it for untrusted code.
- Networked Docker mode uses bridge networking. The harness has no transparent proxy or network namespace firewall that enforces per-domain egress rules.
- A browser click is explicit consent for a manual web request, but this app does not enforce network policy outside its own web tools.
- No native Windows token/job-object sandbox, OS secure store, MCP client, headless browser automation, Git worktree manager, durable job queue, general host-shell tool or desktop control is enabled.
- Plugin `read_only` declaration is not technically enforceable; plugin services run outside the command sandbox.
- Deterministic adaptive routing is a heuristic, not a trained optimizer or a benchmark win.
