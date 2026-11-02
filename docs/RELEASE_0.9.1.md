# Release notes — Indra Lok Meta 0.9.1

## Added and strengthened

- **Extension seams:** Markdown-only workflow skills and declarative local HTTP JSON plugin manifests. Skills are bounded instruction text; the host does not import plugin code. A plugin must pass both a global environment gate and its own enabled manifest flag.
- **Built-in workflow library:** academic literature review, evidence-based code review, debugging/regression, local model benchmarking, research planning, research replication, safe data analysis, safe web extraction, study coaching, task graph planning, web research and secure plugin development.
- **Bounded web research:** public HTML/text/JSON extraction, source URLs, robots.txt policy, bounded search-and-fetch, same-host crawling, byte/page/text/time caps, redirects revalidated, source allowlist enforcement and explicit SSRF limitations.
- **Parallel task execution:** independent read-only subagents and a dependency-aware DAG. The graph rejects duplicate IDs, unknown dependencies and cycles before model calls; dependencies receive bounded untrusted outputs; failed parents skip dependent nodes.
- **Optional Docker runner:** sanitized text-only snapshot, no workspace bind mount, no network, read-only container root, capability drop, non-root user command, RAM/CPU/PID/time/output limits and no automatic write-back. Disabled by default; requires a local image and a functioning Docker Desktop/WSL2 setup.
- **Product reliability:** Windows setup now compiles, runs regression tests, checks JavaScript syntax when Node is present, and validates the skill/plugin registry before marking dependency setup complete.

## Verification in the build environment

- 76 unit/API/security tests passed.
- Python compilation passed.
- Frontend JavaScript syntax check passed.
- Skill/plugin validator found 12 skills and one disabled, valid example plugin manifest.
- The five-case deterministic routing smoke evaluation selected the expected profile in all five cases. This is a router regression only, not evidence of improved model task success.
- Core FastAPI liveness and route smoke checks passed in the current environment.

## Not verified here

- PowerShell scripts were not executed on a real Windows desktop.
- A browser binary was not installed in this environment, so Playwright visual/UI interaction tests could not run; the browser JavaScript was syntax-checked.
- Docker CLI/daemon was unavailable, so the sandbox was unit-tested but not exercised against a real container runtime.
- No model inference result was claimed unless the configured provider was reachable. The actual llama-swap/llama.cpp endpoints and GPU workload must be verified on the user's PC.

## Trust boundary notes

This project is a local single-user workstation, not a hardened multi-user server. Plugin `read_only: true` is a manifest assertion and does not prove that a service has no side effects. DNS/IP validation in the web fetcher is not a network firewall and does not completely eliminate DNS rebinding. Do not expose the local server or plugin services on a LAN, and keep secrets/trace exports private.
