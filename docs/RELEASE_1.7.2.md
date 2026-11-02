# Indra Origo 1.7.2 — security hardening audit

## Changes in this release
- Added remote-only token sign-in for private Tailscale `.ts.net` traffic. The setup script creates 256 bits of randomness when token is missing/short; the disable flow now clears the token to revoke existing sessions.
- Session cookies are host-bound HMACs, expire after 12 hours, and use `Secure`, `HttpOnly`, `SameSite=Strict`, path `/`. Rotating `INDRA_REMOTE_ACCESS_TOKEN` invalidates previous sessions.
- Missing/short token configuration fails closed. Unauthenticated requests to the app redirect to the sign-in page; unauthenticated APIs return 401. The local loopback development path remains unchanged.
- Android URL validation accepts only root-level HTTPS Tailscale addresses, rejects cleartext HTTP/custom ports/path/query/fragment/userinfo, and checks full scheme/host/effective-port before keeping navigation in the trusted WebView. Login-page state is not falsely labeled connected. Added an explicit remote sign-out control.
- Login bodies are streamed and capped at 4 KiB before form parsing; remote responses force `Cache-Control: no-store` and host-only HSTS, including middleware denials.
- Replaced deprecated FastAPI shutdown hooks with a lifespan handler.
- Updated direct dependency pins to reviewed release versions (FastAPI 0.162.0, Uvicorn 0.54.0, pypdf 6.21.2, cryptography 50.0.2). The dependency versions could not be installed in this offline environment; runtime tests below used preinstalled versions and must be repeated after a clean dependency install. Upstream published additional pypdf resource-exhaustion advisories on 2026-10-27, after pypdf 6.21.2 was released, so PDF parsing is now disabled by default pending a patched release and renewed review. Set `INDRA_ALLOW_UNSANDBOXED_PDF=true` only for trusted PDFs when accepting the residual in-process parsing risk.
- Updated remote-access/security docs, version surfaces, and regression tests.

## Verification performed
- `python -m pytest -q`: 190 tests passed, zero warnings, 16 subtests passed, using the preinstalled runtime environment.
- `python -m py_compile app/main.py`: passed.
- `node --check app/static/app.js`: passed.
- `python scripts/validate_extensions.py`: passed, 12 skills and the disabled example plugin validated.
- Static HMI source audit: see `SECURITY_AUDIT_1.7.2.md`; it is a heuristic source scan, not an external penetration test.
- Release ZIP inventory check: excludes `.env`, SQLite databases, signing keys, Android keystores, `local.properties`, build directories and Python bytecode.

## Explicit limitations / not verified
- Windows PowerShell script was reviewed but not executed on Windows in this environment. Android has no compiled APK in this release; Android SDK/Gradle and physical-device testing were unavailable.
- Live Tailscale Serve / ACL / mobile-data flow was not exercised. Configure and inspect the actual tailnet before enabling.
- Remote single-user workstation remains unsuitable for untrusted users or shared tenancy. Local processes running as the same OS user are outside the security boundary.
- Web-fetch DNS validation has a DNS rebinding/TOCTOU limitation documented in `docs/SECURITY.md`; high-assurance use needs OS/network egress enforcement.
- No absolute security claim is made; dependencies and host OS must be kept updated and the deployment-specific threat model still matters. There has been no independent penetration test, SAST/SCA execution, or real-device/network adversarial validation in this environment.
