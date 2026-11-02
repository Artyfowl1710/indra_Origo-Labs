# Known limitations and roadmap

## Release 1.7.2 limitations

- Windows-first and single-user. No multi-user roles, SSO or shared-team tenancy.
- Android companion source is included, but this release archive does not include a compiled, signed or device-tested APK.
- Remote Tailscale + mobile-data flow was not tested end-to-end in the preparation environment.
- Dependency installation against the exact release pins did not complete in the offline preparation environment. Reinstall and test in a clean environment before relying on the release.
- PDF parsing is disabled by default because upstream parser resource-exhaustion advisories remain open for the pinned release.
- URL validation does not eliminate DNS rebinding/SSRF. Stronger egress controls need OS/firewall/proxy configuration.
- Docker sandbox safety depends on the Docker daemon, host kernel, image and runtime configuration; the network escalation mode has broad outbound reachability.
- RAG citation provenance is not proof of truth. Retrieval quality must be evaluated on representative user data.
- HMI static checks are heuristic, not a human study or accessibility certification.
- No independent penetration test, broad fuzzing campaign or full SAST/SCA scan has been completed.

## Recommended roadmap

### Before personal remote use
- Validate exact dependency pins in a clean environment.
- Test Tailscale Serve and token rotation on a dedicated Windows machine.
- Compile the Android app and run a physical-device checklist.
- Add rate limiting/backoff for remote login and audit remote authentication failures.

### Before broader distribution
- Independent threat-model review and penetration test.
- Resolve SSRF DNS-rebinding risk with connection-pinned DNS or an egress proxy/firewall.
- Re-enable PDF ingestion only after a patched parser and adversarial corpus tests.
- Add CI dependency/SAST/secret scans and an SBOM/provenance attestation.
- Add reproducible Android release build and signed release artifact handling.
- Conduct keyboard, screen-reader and mobile usability studies.
- Establish a supported upgrade/migration policy for SQLite schemas and user data.
