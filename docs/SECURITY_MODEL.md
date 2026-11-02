# Security model and threat model

## Classification

Origo is a local-first, single-user workstation intended for personal use. It is not a hardened multi-tenant server. Security relies on a combination of application controls, OS account permissions, trusted local services, user approvals and conservative defaults.

## Assets

- API/provider credentials and the remote access token.
- Conversation history, prompts, model responses and run traces.
- Workspace files, approved edits, backups and exports.
- Indexed document content and RAG metadata.
- Local model endpoints, Docker daemon and plugin services.
- Remote access to the workstation while the PC is running.

## Threat actors and scenarios

| Threat | Relevant control | Residual risk |
|---|---|---|
| Malicious prompt or model-generated tool request | Bounded tools, policy checks, explicit approvals, run budgets | Model can still make bad suggestions; approval fatigue and logic bugs remain possible |
| Prompt injection inside a retrieved document or web page | Treat sources as untrusted evidence; source citations; approval gate | A user/model may still be influenced; citations do not establish truth |
| Unauthorized remote client | Tailscale private network, token sign-in, host-bound signed 12-hour cookie, restrictive ACLs | Tailnet misconfiguration, stolen token/device, single-user session design |
| Malicious PDF causing resource exhaustion | PDF parsing disabled by default | Enabling in-process parser restores exposure; upstream advisories may change |
| Malicious workspace file/path | Type/path filters, bounded reads, hash-checked proposals | Same-user filesystem races and parser bugs remain |
| SSRF/DNS rebinding | Public-address validation, redirects revalidated, scheme/domain controls | DNS validation and connection can race; OS/proxy egress policy needed for high assurance |
| Dangerous code execution | Docker sandbox disabled by default; no host-shell fallback; no network by default | Docker daemon, image, kernel, runtime and optional network mode are trusted |
| Malicious plugin | Plugins disabled by default, manifest declaration, loopback endpoint policy | `read_only` is not proof of safety; enabled service has its own behavior |
| Secret committed to Git | `.gitignore`, release archive excludes `.env` and local data | User can override ignore rules or commit another secret; run secret scanning |
| Same-user malware/process | Loopback binding and OS-level user separation | Same OS user can often inspect local state or access endpoints |

## Remote access requirements

- Use Tailscale on the PC and phone; require MFA on the identity provider and restrictive tailnet ACLs.
- Use Tailscale Serve for private HTTPS. Do not use router port forwarding or public reverse proxies.
- Set `INDRA_REMOTE_ACCESS_ENABLED=true` only after reviewing who can access the tailnet and generating a high-entropy token with the setup script.
- Keep the token in `.env` only; never store it in Android preferences or Git.
- Rotate token and restart Origo if exposure is suspected. Verify Serve status after disable operations.
- PC must be awake, connected and running Origo/Tailscale. Remote access does not wake a sleeping PC.

## Safe defaults

- Bind loopback for local mode.
- Agent network policy `ask` or `deny`.
- Docker sandbox off until configured; networking off by default.
- Local HTTP plugins off.
- Dense embeddings off unless explicitly configured.
- PDF parsing off.
- Do not commit `.env`, `data/`, `workspace/`, logs, backups, tokens, keystores or APK signing credentials.

## Incident response

1. Stop Origo and disable remote access if you suspect unauthorized use.
2. Disconnect/revoke unknown Tailscale devices and review ACLs/device approvals.
3. Rotate `INDRA_REMOTE_ACCESS_TOKEN` and provider keys; restart the service.
4. Preserve logs privately for investigation, then inspect unexpected sessions, run traces, file changes and Docker containers.
5. Restore changed files from verified backups only after inspecting them.
6. Reinstall from a known release if source integrity is in doubt; do not trust an archive solely because it is signed locally.

## Audit limits

See `SECURITY_AUDIT_1.7.2.md`. Tests and source scans are useful but do not establish absence of vulnerabilities/backdoors. Windows/Tailscale/Android/Docker runtime tests, clean dependency installation, external SAST/SCA, fuzzing and independent penetration testing remain outstanding.
