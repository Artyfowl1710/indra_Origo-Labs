# Indra Origo v1.7.2 — security and reliability audit

**Audit date:** 2026-10-29  
**Scope:** source-level review of the local API, remote access gate, file ingestion/RAG, tool execution boundaries, Android WebView configuration, extension configuration, dependency pins and test/build surfaces. This is not a certification or an independent penetration test.

## Executive summary

Several concrete issues were hardened in this release. Remote Tailscale access now has an Origo-specific token and a short-lived signed session cookie, login request bodies are capped before parsing, sensitive remote responses are marked no-store, and a synthetic test host is not accepted from an ordinary network client. PDF parsing is off by default because the current latest pypdf release has additional resource-exhaustion advisories published after its release.

**No obvious backdoor-style construct was found in a targeted source scan** for `eval`, `exec`, `shell=True`, `os.system`, `pickle.loads`, unsafe YAML loading, disabled TLS verification, or wildcard CORS in app/tests/scripts/Android. The only shell-process pattern found is the documented Docker sandbox runner. This narrow scan cannot establish that the whole codebase is free of malicious behavior.

## Findings and fixes

### Fixed in 1.7.2

- **Remote access lacked a separate Origo sign-in boundary.** Tailnet membership alone was previously the primary gate. Remote `*.ts.net` access now requires `INDRA_REMOTE_ACCESS_ENABLED=true` plus a token of at least 32 characters (the helper generates 256 bits of random token). Successful login issues a host-bound HMAC-signed 12-hour cookie with `Secure`, `HttpOnly`, `SameSite=Strict`, and path `/`. Rotate the token to invalidate previous cookies; the disable script clears the token.
- **Login request-size handling.** The login handler now streams the request body with a hard 4 KiB cap before form parsing; oversized bodies are rejected.
- **Remote response caching / transport headers.** Remote responses, including denials, receive `Cache-Control: no-store`; HSTS is host-only (`max-age=31536000`) to avoid applying HSTS to unrelated `*.ts.net` tenant domains. CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy` are added as defense in depth.
- **Host-header test bypass.** The synthetic `Host: testserver` is allowed only when the ASGI client is Starlette TestClient's synthetic `testclient`; normal network clients cannot use it to satisfy the loopback host guard.
- **Session lifecycle.** Added explicit sign out and switched FastAPI cleanup to lifespan management.
- **PDF parser risk.** Chat attachment and RAG PDF parsing are off by default while upstream pypdf resource-exhaustion advisories remain open for the currently pinned release. Explicitly enabling `INDRA_ALLOW_UNSANDBOXED_PDF=true` opts back into in-process parsing and must be limited to trusted inputs.

### Existing defense-in-depth controls reviewed

- Supported Windows launcher binds Uvicorn to `127.0.0.1`, not `0.0.0.0`. Remote reachability is intended through Tailscale Serve, not port forwarding.
- Workspace file access uses path/sensitive-file filtering and allowlisted text extensions. RAG has byte/chunk/document bounds and strips common credentials. Secret scrubbing is best-effort, not a full DLP scanner.
- Proposed file edits remain approval-gated and reject stale target content; writes are staged with backups. A filesystem race with another same-user process remains possible.
- The optional Docker command runner is gated and runs a disposable text-only workspace snapshot with networking disabled by default, no host workspace bind mount, read-only root, non-root user and resource limits. Docker Desktop/daemon and host kernel remain trusted components.
- Skills are Markdown instructions, not executable skill code. Plugins are disabled by default and use declared local HTTP JSON services; a `read_only` declaration is an author promise, not proof of no side effects.
- Android is HTTPS-only for root-level `*.ts.net` hosts, rejects custom ports and URL decorations, keeps navigation on the configured origin and routes unrelated external HTTPS URLs to the system browser. It is a WebView companion, not a compiled APK in this release.

## Verification run

- `python -m pytest -q`: **190 passed, 16 subtests passed**.
- `python -m unittest discover -s tests -q`: **190 passed** (the Windows launcher uses unittest).
- `python -m compileall -q app tests scripts`: passed.
- `node --check app/static/app.js`: passed.
- `python scripts/validate_extensions.py`: passed; 12 skills, 1 disabled example plugin, no plugin endpoint contacted.
- HMI static source heuristic: **24/24 checks pass, 0 warnings, 0 failures**. This is not WCAG conformance or a human usability study.
- Targeted source scan for common dangerous execution patterns returned only the intentional sandbox `subprocess.Popen` path. This is not a full static-analysis engine.

## Important unverified or residual risks

1. **Dependency install was not verified.** The offline runtime had FastAPI 0.128.2, Uvicorn 0.48.0, pypdf 5.9.0 and cryptography 46.0.4, while `requirements.txt` now pins FastAPI 0.162.0, Uvicorn 0.54.0, pypdf 6.21.2 and cryptography 50.0.2. Network/DNS prevented installation; tests ran against the installed environment, not the declared new versions. `pip check` reports an unrelated shared-environment conflict: `moviepy 2.2.1` requires `pillow<12`, but Pillow 12.3.0 is installed.
2. **pypdf residual.** The pypdf release page lists 6.21.2 dated 2026-10-21, with fixes for repeated full-file loads and oversized xref tables. The upstream advisory page lists additional resource-exhaustion advisories published 2026-10-27. The PDF feature gate is a temporary conservative control, not a claim that all pypdf vulnerabilities are fixed. Re-check advisories and obtain a patched release before enabling PDF parsing for untrusted sources.
3. **SSRF / DNS rebinding.** URL validation resolves public DNS/IP addresses separately from the eventual socket connection, leaving a DNS rebinding/TOCTOU gap. For high assurance, enforce outbound egress restrictions at the OS/firewall/proxy layer.
4. **Single-user trust model.** Any local process running as the same OS user may be able to access local endpoints and files. This is not hardened multi-user tenancy; do not expose direct public/LAN ports. Tailnet ACLs and MFA are still important.
5. **Platform tests not run.** Windows PowerShell remote setup/disable was reviewed but not executed; Android SDK/Gradle build and physical-device validation were unavailable; real Tailscale Serve + mobile-data flow was not tested; Docker sandbox was not exercised against a running daemon. No APK is included.
6. **No third-party security gates.** `pip-audit`, Bandit, Ruff and external SAST/SCA scans were not installed/run here. No independent penetration test, fuzzing campaign, threat-model workshop, or malicious PDF stress test was performed.
7. **Operational security still matters.** Keep `.env`, SQLite state, histories, backups and exports private. Hosted model endpoints may receive prompts/context. Rotate remote tokens if exposed, inspect Tailscale Serve status after disabling, and keep the host OS/Python/browser/model runtime updated.

## External references checked on audit date

- [pypdf releases (6.21.2 dated 2026-10-21)](https://github.com/py-pdf/pypdf/releases)
- [pypdf security advisories](https://github.com/py-pdf/pypdf/security/advisories)
- [PyPI provenance for pypdf 6.21.2](https://pypi.org/project/pypdf/6.21.2/)
- [Uvicorn release notes (0.54.0)](https://uvicorn.dev/release-notes/)

## Release recommendation

**Conditional local/personal testing only.** Keep the supported loopback binding and tailnet ACL, do not port-forward, leave PDF parsing off, and install the pinned dependencies in a clean environment before relying on this release. This audit found/fixed concrete gaps but does not warrant a claim that the entire product is vulnerability-free.
