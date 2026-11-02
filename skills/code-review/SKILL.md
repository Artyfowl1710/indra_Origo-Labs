---
name: Evidence-based Code Review
description: Review code for correctness, security, reliability, and test gaps with concrete evidence.
---
# Evidence-based Code Review Skill

1. Inspect project structure and the actual code paths before making claims. Cite workspace-relative file names and observed symbols/conditions.
2. Prioritize bugs by severity, likelihood, impact, and confidence. Separate confirmed defects from hypotheses.
3. Look for authorization bypasses, path traversal, SSRF, unsafe deserialization, secret leakage, race conditions, resource exhaustion, weak error handling, and inadequate tests.
4. Trace data from input to side effect. Prefer narrow fixes and regression tests.
5. Never run arbitrary host commands. Use `sandbox_run` only when explicitly available and Docker sandbox is enabled; its changes are disposable and not applied to the source workspace.
6. Never apply changes directly. Use `propose_write` and explain the diff, tests, risk, and rollback.
7. Report what was tested, what was not, and exact reproduction steps. Do not claim tests passed without actual results.
