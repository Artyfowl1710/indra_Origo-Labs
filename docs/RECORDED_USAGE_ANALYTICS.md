# Recorded token usage and cost coverage

Open **More → Analytics** or **Models** in the native Indra app. Usage is visible by default, without editing YAML. Models offers a local hide/show control. The current screens no longer hide recorded usage behind the legacy `dashboard.show_token_analytics` flag. The setting remains for older-client compatibility.

## What changed

Both reports now use the same recorded-usage calculation. Main per-model/provider deltas retain attribution when the conversation changes models. Auxiliary task rows, including vision and compression, are included once in daily, model, task and headline totals. A main-session summary can fill a positive gap in main-route records; auxiliary usage never subtracts from that main gap. Reported model details are retained if a session summary is behind them. Profile changes reset the view and explicitly scope its requests.

Input counters represent uncached input. Total tokens include input, output, cache reads and cache writes. Reasoning tokens are a subset of output and are not added again. Model charts now show disjoint reasoning/other-output segments, include cache writes and use the current theme's colours. The coverage card shows cache buckets and task counts separately.

Completed main and auxiliary responses without a usage block are counted as calls with unknown token/cost amounts. Available auxiliary pricing status is preserved. Unpriced usage is labelled unavailable or partial rather than presented as free. Estimated cost is separate from reported billed amounts; missing billed cost is not a zero-dollar invoice.

The reporting queries read an internally consistent SQLite snapshot. They do not alter the current transcript, model requests, prompt prefix or system prompt, and do not send telemetry elsewhere. API responses omit billing endpoint URLs and contain no prompts or credential fields.

## Important limits

- The existing database stores cumulative route counters, not a full history of physical HTTP attempts. Failed requests, internal SDK/provider retries and unrecorded service/media calls can have unknown usage and spend. They are not silently assigned guessed tokens. The displayed call count is recorded completed work, not every network attempt.
- Aggregated pricing status cannot prove that every historical call was priced. Missing usage mixed into a later priced row may not remain separately identifiable. Costs remain incomplete estimates unless independently reconciled with a provider invoice.
- Daily groups and reporting-window membership follow the **conversation's start date in UTC**. Historical route totals cannot be accurately split across individual request dates. Long-running conversations that began outside the window are outside this report.
- Older sessions can have only a session summary. That residual is attributed to the summary's stored model/provider, so its original model split may be unavailable. The coverage panel reports residual and inconsistent-summary counts.
- Unknown or zero token counters do not prove that a call consumed no tokens. Auxiliary calls outside an active session-accounting context are not assigned to a guessed conversation.

Full per-attempt recording, provider invoice reconciliation, complete media/service accounting and actual request-date histories remain open in the product objective. These reports expose current evidence and its limits.

## Verification

Passed 307 product tests (two skips), 67 focused accounting/backend tests, two existing analytics API tests, 19 frontend tests and 49 isolated desktop checks, plus build and required validation.

The real agent/SDK fixture uses a loopback provider that first returns HTTP 429, then a correctly framed streaming response. A normal auxiliary call follows through the auxiliary client. Both usage blocks reach the database and reporting calculation with correct cache totals. The receiver sees more physical attempts than the recorded completed-call count; the test verifies that the report discloses this retry limitation. No cloud key or external inference is used.

Other checks cover model switching, same-model auxiliary work, missing usage, legacy summaries, asynchronous queue draining, profile boundaries, authentication, date limits, read-only reporting and avoiding double-counted residuals. Native checks verify visible navigation, main/vision task rows, cache writes, partial-cost labels, identical Models/Analytics totals and narrow layouts. Synthetic fixture data is seeded only inside a guarded temporary desktop-test profile. The main app session and SIH reference folder are unchanged; the rebuilt UI and backend load together on the next normal launch.

Local verification files are under `data/test-results/usage-analytics-*`; the rendered view is `indra-recorded-usage.png`. See [the full product acceptance ledger](PRODUCT_GOAL_ACCEPTANCE.md) for remaining scope.
