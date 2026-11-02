# Project goals and quality checks

In Chat, choose a project folder, then select **Set project goal** in the sidebar.

Specify the outcome, completion evidence, project rules, constraints and when the agent should stop and ask. Set a turn limit and optional quality-check commands with their timeout and retry limits. Saving creates a **paused** goal. Review it and choose **Start goal** to begin. **Pause** stops automatic continuation and interrupts the current session; **Edit goal** becomes available when the current run has stopped.

The goal, criteria, check results, exit codes, output tails and check timestamps are stored with the chat in the active local profile. A saved draft appears in Sessions and can be reopened. The turn-budget bar reports resource usage, not a fabricated percentage of task completion. Project rules in the completion contract guide the agent; permissions and execution policies remain separate controls.

Checks use the same terminal tool as ordinary agent commands: the selected local, Docker or remote backend, its working folder, approval rules, cancellation, output redaction and timeout handling. A refused or unavailable backend cannot fall back to an unrelated host shell. Docker tests see the workspace mounted for that session. A failed check prevents completion and returns its diagnostics to the next agent turn. Repeated failures exhaust the configured retry limit and pause the goal. Checks run again against the actual environment; an old host git-status result does not substitute for a fresh test.

Saving does not execute check commands or call a model. Starting and continuing a goal uses the selected model and can incur provider charges. The normal model/tool approvals remain in effect. A paused goal or a replacement entered while a check/judge was running prevents that old evaluation from continuing the previous objective.

## Commands

- `/goal <objective>` accepts inline `verify:`, `constraints:`, `boundaries:` and `stop when:` fields.
- `/goal status`, `/goal show`, `/goal pause`, `/goal resume`, `/goal clear`.
- `/goal gate list`, `/goal gate add <command>`, `/goal gate remove <number>`, `/goal gate clear`.

The editor accepts up to 12 checks, each at most 2,000 command characters, 1–300 seconds and 0–5 retries, and a turn budget from 1 to 200. Explicit CLI-only wait/draft controls remain unavailable through the desktop command surface and return an error without replacing the current goal.

## Developer contracts and evidence

Authenticated session JSON-RPC exposes `goal.get` and `goal.configure`. Configuration requires an idle session and bounded objective/criteria/check fields. Editing an existing goal requires its current `expected_created_at` revision; stale edits fail rather than overwrite another change. Goals use the existing GoalManager and profile `state.db`, without a second goal database or mid-conversation system-prompt mutation.

Real acceptance includes desktop form save/edit/reopen, scoped profile isolation, pause/replacement during blocking evaluation, and a Docker repair fixture. The Docker fixture uses the actual terminal/check runner and a synthetic judge: a broken file fails the check, a repaired file is rechecked successfully, output persists, and a refused execution policy produces no host-side fallback marker. This proves the workflow plumbing and isolation test; it does not prove an arbitrary language model can finish every coding task or replace independent security testing.

Local reports are in `data/test-results/goals-workflow-*.log`, `goal-workflow-native-acceptance.json` and `goal-execution/acceptance.json`.

A subsequent real-model probe passed with local Qwen3.5, a real local completion judge and Docker file/terminal tools. Starting from a broken invoice module, it read the project, wrote and patched the source, reran tests and finished its goal. Nine fixed tests cover quantities, discounts, Decimal rounding, empty inputs and precise upper/lower discount boundaries. An independent Docker rerun passed all nine; test/README hashes and the source inventory confirmed that only the permitted module changed. This small fixture establishes an actual coding/edit/test path, not a guarantee of correctness for arbitrary projects or production financial software. The report is `data/test-results/real-project-goal/acceptance.json`.

The same fixture also passed with the content-trust guard enabled and nine restricted review requests, including a native-renderer approval receipt. The fixture's reviewer is automated and limited to that test project; production review requires a person. The judge now receives bounded runtime check commands, timestamps, exit codes and redacted output tails. This avoids repeating completed work simply because the assistant's prose omitted test output. Passing checks remain evidence only for what they verify, and failed checks still prevent judging/completion. These auxiliary evidence messages do not rewrite the cached conversation prefix. See `data/test-results/real-project-goal-guarded/acceptance.json`.
