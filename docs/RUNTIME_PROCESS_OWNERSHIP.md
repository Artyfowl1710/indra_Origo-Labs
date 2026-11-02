# Runtime crash cleanup

Origo's long-lived Windows model and phone-sharing services now require strict kernel job containment. A supervisor must establish its job before spawning its service, and then explicitly assign the child's existing process creation handle. Assignment failure stops that child instead of reporting the service ready.

The implementation extends the imported `hermes_cli.process_identity` helper with an opt-in strict mode and correct pointer-sized Windows HANDLE declarations. Existing callers keep their default breakaway behavior. Strict callers disallow explicit and silent breakaway and refuse an already-attached weaker job. Origo does not look up a child by executable name or reopen a potentially reused PID to attach it.

Why explicit assignment matters: the initial real-process probe found that a child launched through this machine's packaged Python runtime was not in the inherited job. The corrected probe queries actual job membership and assigns native services through their creation handles. The fixture also checks that native descendants remain contained. This avoids treating a successful spawn or assumed parent relationship as proof of cleanup.

Windows documents that [kill-on-close jobs terminate their associated processes when the last job handle closes](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects). The supervisor keeps its non-inheritable job handle for its own lifetime. Abrupt termination closes that handle in the kernel, so cleanup does not depend solely on Python `finally` blocks. The model gateway still keeps its desktop-parent watcher for normal owner loss; the sharing supervisor still owns only a foreground Serve session.

## Verified on 31 October 2026

- Three real Windows process tests passed: abrupt owner death reaps native child/grandchild workers while an unrelated process survives; normal owner exit reaps its workers and rejects explicit breakaway; a weaker existing job is not accepted as strict.
- A real signed llama.cpp server loaded the reference Qwen text model in CPU mode in an isolated fixture. Force-killing its owner reaped the server, closed its loopback health endpoint and spared an unrelated fixture process. The probe completed in 11.56 seconds, including setup; this is not an inference latency benchmark. Receipt: `data/test-results/model-crash-live.json`.
- Sixteen routing/lifecycle contract tests and seven sharing contract tests passed, including startup refusal when a job cannot be created or assigned, and cleanup when a worker exits during termination.
- The imported core's canonical runner passed 29 existing process-identity/Windows gateway teardown regressions.

This extends process-lifetime guarantees, not execution permissions. Docker isolation and approval gates are unchanged. The active app, its GPU model and phone sharing configuration were not stopped or altered by the crash fixtures. Live phone testing remains deferred at the user's request.

## Remaining acceptance

The current adapter uses CPython's Windows Popen creation handle, including the asyncio subprocess transport. Re-run the real process-tree and signed-model crash probes when changing the packaged Python version. Actual Tailscale publication and device behavior, GPU-memory recovery measurement, clean-machine packaging and the complete release audit remain open.

Final repository gates passed: 225 regression tests (two skips), compilation, extensions, desktop/legacy JavaScript syntax, native IPC checks and fixture PowerShell syntax. The selected SIH-26-main reference baseline remained unchanged.
