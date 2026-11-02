# Product positioning and capability comparison

Indra Origo is aiming at a practical, local-first coding/research workstation with a replaceable model layer. It is not a clone or official implementation of Codex, Google Antigravity or Claude Code. Their behavior and availability vary by product, OS, plan and version. This document compares capabilities at a category level; it is not a benchmark.

## Capability matrix

| Capability | Indra Origo 1.0.0 | Commercial coding-agent category | Current boundary |
|---|---|---|---|
| Use a configurable OpenAI-compatible inference server | Yes | Common | Provider must be compatible; no model included |
| Stream model output | Yes | Common | End-to-end latency depends on provider/model |
| Ask/deny control for agent web calls | Yes; ask by default, block option, one-session hostname grant | Common | Explicit manual web buttons use a separate confirmation; not an OS network policy |
| Run commands in an isolated environment | Optional Docker container | Common | Linux-container semantics; snapshot is sanitized and not bind-mounted; no real Docker run was verified in this build environment |
| Outbound network denial by default for command sandbox | Yes (`--network=none`) | Common | Networked mode uses Docker bridge and is broad—not domain-allowlisted |
| Native Windows OS-enforced sandbox | No | Some tools provide one | Docker Desktop/WSL2 is the current isolation boundary; do not treat it as equivalent to native process sandboxing |
| Edit approval with diff, backup and undo | Yes | Common | Proposed text changes only; races with unrelated host processes cannot be eliminated fully |
| Project context selection | Bounded context pack + one-turn attachment | Common | No semantic indexing is performed automatically |
| Parallel tasks / dependency graph | Bounded read-only child agents | Common in advanced agents | No durable distributed scheduler, worktree isolation or persistent child-agent sessions |
| Skills | Markdown workflows | Common | Instructions only; reviewed before use |
| Plugin/connectors | Declarative local HTTP JSON tools | Common | Loopback only; no general MCP client; plugin `read_only` is a trust assertion |
| Browser automation | No | Available in some products | Static public fetch only; no JavaScript browser, authenticated web app automation, or remote-control bridge |
| Git integration | Read-only status/diff inspection | Common | No automatic branch/worktree manager, commits or pushes |
| Background jobs / scheduled tasks | No durable task scheduler | Available in some products | Runs are in-process; restart loses in-flight tasks |
| Learned self-improving harness | No | Research area / product-specific | Deterministic profiles and small routing regression only |

## Design principles

1. **Model is not the policy authority.** The model proposes a tool call; the harness validates inputs and decides whether to ask, deny or execute inside a bounded capability.
2. **Sandbox and approval are separate layers.** A human click does not make a broad permission technically safe; the execution boundary must still constrain the operation.
3. **Low-risk local actions should be predictable.** Read-only workspace actions can remain smooth, while network access, plugins and sandbox execution use visible, scoped consent.
4. **Changes return as diffs.** The sandbox never writes directly into the real project. Candidate changes flow through the normal proposal/approval mechanism.
5. **Measure before claiming improvement.** Versioned traces, policy fingerprints and regression tests are operational foundations. They do not show that one model or harness completes tasks better until measured on repeated, held-out tasks.

## Reference behavior to learn from

- OpenAI's official Codex safety guidance separates the technical sandbox boundary from approval policy and describes controlled network access and approvals for exceptional requests: https://openai.com/index/running-codex-safely/
- OpenAI's Windows sandbox engineering write-up emphasizes restrictions enforced at the operating-system/process boundary: https://openai.com/index/building-codex-windows-sandbox/
- Google Antigravity documents a Deny/Ask/Allow permission engine and sandbox/permission presets: https://www.antigravity.google/docs/permissions and https://www.antigravity.google/docs/sandbox-mode

Indra borrows these high-level design principles, but its implementation is narrower. In particular, Docker bridge networking is not domain filtering, and application-level checks are not a substitute for operating-system enforcement.
