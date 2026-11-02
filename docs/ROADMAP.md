# Roadmap

## Implemented in v1.0.0

- [x] OpenAI-compatible inference adapter, model discovery, SSE output streaming and bounded tool-call reconstruction
- [x] Adaptive fast/balanced/deep budgets, explicit run-state transitions, structured traces and SQLite persistence
- [x] Saved conversations, research exports, workspace search/context packs, approval-gated writes, verified backups and conflict-aware undo
- [x] Read-only Qdrant retrieval when explicitly configured
- [x] Declarative Markdown skill registry and loopback HTTP JSON plugin manifests; extension validator and skill-scaffold helper
- [x] Public web search, static-page extraction, bounded search-and-fetch research and same-host crawling with HTTPS-first policy, robots.txt, domain allowlist, rate limits, size/time/page caps and redirect checks
- [x] Parsed robots policy caching that evaluates each path independently; domain allowlist validation that fails closed on malformed configuration
- [x] Independent parallel read-only tasks and a dependency-aware task DAG with cycle validation, dependency-result context, cancellation cleanup, bounded per-parent task count and cross-request child concurrency
- [x] Optional Docker sandbox with disposable sanitized text-only staging, no host workspace bind mount, no network, non-root user commands, dropped Linux capabilities, resource limits, bounded output and no automatic write-back
- [x] Windows setup/launch/stop scripts, diagnostics, offline regression suite, model smoke probe and deterministic routing check
- [x] Built-in Markdown skills for task graphs, literature review, code review, debugging/regression, replication, safe data analysis, plugin development, local inference benchmarking, research planning, study coaching and safe web extraction

## Implemented in v1.6.0

- [x] Optional, editable, removable per-run outcome ratings with local aggregate counts and clear-all control; no prompt/answer text in the feedback table and no model/training/adaptation path. See `OUTCOME_REVIEW.md`.
- [x] Explicit HMI/agent behavioral matrix with positive and negative expectations, plus regression tests for data isolation, optionality, correction, deletion and unsafe UX patterns. See `HMI_BEHAVIOR_MATRIX.md`.

## Next high-value work

- [ ] Capsule replay in a disposable no-network sandbox with per-artifact diffs and explicit nondeterminism reporting
- [ ] Exporter-level Proof Ledger integration for Markdown/DOCX/PPTX/XLSX/PDF, with conservative registered-claim coverage and no “verified” badge unless checks pass
- [ ] Cross-machine Capsule verifier, pinned signer fingerprints and Windows ACL/key-rotation/recovery tests
- [ ] Real browser keyboard/focus testing plus screen-reader and reduced-motion validation against WCAG 2.2; run formative usability sessions on core workflows

- [ ] OS-backed network egress proxy/firewall so approved domains are enforced technically, not just through URL validation
- [ ] Native Windows process isolation (restricted token, Job Objects, ACL enforcement) or documented WSL2 bubblewrap profile; do not claim Docker equals native sandboxing
- [ ] MCP client support with audited server transport, capability negotiation, per-tool consent and explicit trust tiers
- [ ] Browser automation only through a separate isolated browser container with user-visible navigation and domain/permission policy
- [ ] Reviewed plugin-manifest signing/trust UI, richer JSON-schema contract tests and explicit human approval for mutating plugin actions
- [ ] Atomic benchmark experiment manifests, repeated trials, held-out tasks, confidence intervals and cost/latency comparisons across harness candidates
- [ ] Optional sandbox artifact import through human-reviewed diffs, patch application, backups and rollback
- [ ] Git-aware context/status/diff adapter and project-specific test commands executed only inside the sandbox
- [ ] First-class notebook/CSV/PDF ingestion with explicit parsers, size limits, cancellation and provenance
- [ ] OS secure-store integration for provider credentials and a hardened authentication boundary before any multi-user or remote access
- [ ] Model-server lifecycle management with process ownership, health recovery, safe stop and explicit VRAM/concurrency management
- [ ] Desktop bridge only after a separate per-action consent system and a dedicated threat model

## Research discipline

The deterministic profile router is a heuristic. `scripts/harness_eval.py` is a small routing regression test, not a benchmark of task completion or a claim that the adaptive harness improves model capability. Before promoting a learned optimizer, compare fixed baseline and candidate configurations on held-out tasks, repeat stochastic trials, and report safety failures, latency/cost and uncertainty. The model cannot raise its own budgets, bypass approvals or change network exposure.

## Current non-goals

No direct host-shell execution, desktop control, Qdrant mutation or arbitrary Workbench business operation is enabled. Docker sandbox execution is optional and isolated as far as the configured Docker environment permits. Web SSRF mitigations are not a substitute for an outbound firewall. Service health does not establish model correctness.


## Sovereign SI OS track (v1.3 direction)

See [`SOVEREIGN_SI_OS.md`](SOVEREIGN_SI_OS.md) for the product architecture and action-permission contract. The v1.3 increment adds a read-only in-app self-test agent (Origo Scout) and the optional Ori companion/break nudges. Email, commerce, Windows-wide automation, offline voice, world-model orchestration and the Capsule/Proof Ledger remain separate milestones; do not advertise them as complete based on the companion UI or Scout route alone.
