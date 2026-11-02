# Indra Origo — Sovereign Intelligence OS direction

**Product thesis:** a user-owned intelligence layer for Windows, distributed as an ordinary application and local service, not a replacement kernel or an always-privileged process. It coordinates models, tools, files, workflows, research environments, and user-approved actions through one inspectable policy boundary.

## Product pillars

1. **Local-first core:** local model router by default; local settings, user-owned memory and project data; explicit provider configuration; export/delete controls; no key material in browser payloads or agent context.
2. **One intent surface:** conversational UI, voice, attachments, file previews, searchable projects, recurring tasks, and notifications.
3. **Specialist workers:** coding, research, email, calendar, shopping, food ordering, astronomy/science, data analysis, tutoring, and desktop assistance use the same typed task interface and policy broker. Specialists propose typed actions; they do not invent permissions.
4. **Connector adapters:** mail/calendar providers, browser/search, delivery and commerce services, astronomy data APIs, local files, Windows UI Automation, and scientific tools are opt-in adapters with declared capabilities, schemas, and health checks. A connector is not enabled merely because a model asks for it.
5. **World/research lab:** reproducible experiments, seeded simulations, parameter sweeps, counterfactual branches, metrics, traces, and evidence-linked claims. Research results remain distinguishable from hypotheses.
6. **Companion layer:** Ori (and future user-selectable characters) provides optional presence, gentle break nudges, and conversation entry points. It must be configurable, quiet by default when disabled, accessible, and compatible with reduced-motion settings.

## Shared action contract

Every external action is a structured request with `intent`, `target`, `payload`, `risk`, `required_permissions`, `preview`, and `undo_strategy` where feasible. A model may recommend actions; only the policy broker decides whether they are allowed. Tool output, email content, webpages, documents, and plugin responses are untrusted data, not instructions that can change policy.

| Level | Example | Default policy |
|---|---|---|
| Observe | Search a selected project, read a connected inbox after permission | Narrow scope; disclose source |
| Draft | Write an email, plan a grocery basket, draft an order | No side effect; show preview |
| Reversible action | Create a draft or save a local note | Ask or use a narrowly configured grant; log outcome |
| External/financial action | Send mail, submit food order, make a purchase, cancel a booking | Explicit per-action confirmation showing recipient/items, amount, and consequences |
| High-impact / destructive | Delete data, transfer money, change account security, broad OS control | Deny by default or require strong confirmation and a narrower separate workflow |

One approval never authorizes later actions. Site content cannot grant permission. OAuth tokens and provider credentials are owned by connector code and never exposed to model prompts. Browser automation, where unavoidable, runs with isolated profiles and narrowly scoped permissions. Operating-system automation must be separately enabled; it is not an implied capability of chat.

## Windows architecture

- **Origo UI:** chat, companion, projects, approvals, notifications, tool results and accessible settings.
- **Loopback service:** session orchestration, job queue, typed tool registry, local policy broker, provider router, and capability manifests.
- **Execution workers:** isolated Python/code execution, browser/desktop adapter, and domain-specific workers. Network egress is deny-by-default where technically possible; local HTTP binding alone is not a complete security boundary.
- **Local data vault:** encrypted credentials managed through Windows Credential Manager or DPAPI in the native packaging phase; separate stores for chat, explicit memory, audit logs, and bulky artifacts; import/export and retention controls.
- **Evidence ledger:** append-only action/approval events with timestamps, connector IDs, input/output digests where appropriate, and artifact links. Secrets should never be copied into logs.
- **Health and tests:** deterministic read-only self-tests, adapter contract tests, model evaluation harnesses, integration tests with fakes, and opt-in live smoke tests.

## Small in-app tester: Origo Scout

Scout is the first self-check agent. It interrogates safe application routes and emits per-check evidence. It intentionally does **not** call an LLM, access external services, mutate settings, write files, or approve actions. Scout is not a replacement for external integration testing, browser end-to-end testing, threat modelling, or live model evaluation.

## Delivery order

1. Deterministic core: Scout, typed schemas, policy broker, audit evidence, safe provider routing.
2. Capsule and Proof Ledger: reproducible exports and evidence-bound claims.
3. Local-first assistant loop: local inference, streaming, tests, cancellation, retries and context budgeting.
4. User-approved connectors: project files, email/calendar drafts, web/search and astronomy feeds.
5. Browser/Windows automation: inspect-only first, then explicit proposals and per-action approvals; no broad unattended control.
6. Commerce and orders: basket previews, item/substitution/fee/price summaries, and explicit confirmation before final submission.
7. Companion, schedules and proactive tasks: configurable reminders, visible job state, quiet hours and interruption budgets.
8. Scientific/world-model studio and education/institution modes.

## Current milestone boundaries (v1.3)

Implemented here: read-only Origo Scout API/UI, a CSS-animated Ori companion, browser-tab active-time break nudges, and this architecture contract. The character and reminders do not control Windows, place orders, access email, or run tasks in the background. Scout is not a model-based planning agent and has not been tested against a running Windows desktop or real external providers. Voice remains browser-provided in v1.2; fully local ASR/TTS and OS-wide desktop automation are not claimed.
