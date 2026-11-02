# HMI and Agent Behaviour Matrix

This matrix turns human–AI interaction principles into testable product expectations. It separates deterministic contract tests from user research and live-model evaluations; the former cannot prove that an interface works well for people.

## Desired behaviours and guardrails

| Situation | Origo should | Origo should not | Existing or v1.6 verification |
|---|---|---|---|
| User asks for a reversible draft | Show a proposal and preserve the source | Silently overwrite an existing file | Approval and stale-file regression tests |
| User requests a consequential external or destructive action | Explain target and consequence; require the relevant explicit approval or deny by default | Infer consent from a prompt, webpage, or earlier approval | Policy/permissions tests and the permission UI |
| Tool or provider fails | Show actionable status and recovery path | Claim the task succeeded or hide the failure | API/provider tests; HMI error-recovery check |
| User wants to cancel a run | Expose cancel and handle the abort | Trap the user in an uninterruptible UI | Stream/cancellation tests and `cancel_long_tasks` audit |
| User doesn't want to rate a response | Continue normally without prompting again | Gate core functionality behind a rating or use guilt/streaks | v1.6 optional-feedback audit and API independence |
| User rates an answer | Persist only the selected label and IDs locally | Send the rating to the model, attach prompt/answer text, train on it, or silently alter behaviour | `tests/test_feedback.py` |
| A rating is wrong | Let the user replace/remove it and clear all ratings | Make ratings permanent or make deletion remove unrelated data | `tests/test_feedback.py` |
| Conversation includes untrusted web/file text | Treat it as data and keep policy/permission decisions outside the model | Let external text grant new permissions | Tool, permissions and policy-boundary tests |
| Model appears confident but evidence is weak | Disclose verification scope and let the user inspect evidence | Equate fluency, a numeric match, or a signed archive with factual truth | Per-answer correctness caveat; Proof Ledger honesty check; evidence integrity tests |
| Long or animated interface is open | Respect reduced motion and offer explicit controls | Autoplay speech/video or nag users to stay engaged | Static HMI checks and reduced-motion CSS guardrail |
| Keyboard or screen-reader user navigates | Provide labels, visible focus, state announcements, and predictable controls | Depend on hover, color alone, or inaccessible custom gestures | HMI static checks; manual assistive-technology testing still required |
| The user needs a private workflow | Explain which data stays local and when a configured provider receives content | Imply “local-first” means every operation is offline | Data-flow disclosure and provider diagnostics |

## Evaluation method

1. **Deterministic contract tests:** run the automated unit/API suite in CI, including negative tests. Fail the build for policy bypasses, invalid feedback membership, content-bearing feedback summaries, or broken cancellation/approval boundaries.
2. **Static HMI gate:** run `GET /api/hmi/audit`. A pass means only the named source heuristics passed; it is neither a WCAG certification nor a usability study.
3. **Browser integration:** on native Windows, test 100%, 125%, and 200% zoom; 390px viewport; keyboard-only navigation; focus visibility; reduced-motion mode; long text; browser refresh; keyboard escape/cancel; and screen reader labels.
4. **Moderated usability pilot:** recruit representative first-time users. Give realistic tasks without coaching. Measure task success, critical error rate, time-on-task, unnecessary tool calls, number of clarifications, undo/recovery success, comprehension of where data goes, and perceived control. Record observations with consent.
5. **Live-model behaviour evaluation:** use a fixed, versioned set of should-act, should-ask, should-stop, and should-refuse cases. Run deterministic tests with mocks first, then held-out model trials. Inspect transcripts and actual side effects, not just the final text. Report per-case results and uncertainty; do not turn human ratings into a fabricated model-accuracy score.

## Anti-goals

Do not optimize for daily active time, streaks, notifications accepted, or number of tools called. Do not use urgency/scarcity copy, relationship guilt, fake confidence meters, fake “thinking” theatrics, or forced ratings. Do not claim award-winning status, perfect accuracy, complete autonomy, or complete privacy without evidence.

## Source principles

- Microsoft Research, *Guidelines for Human-AI Interaction*: set expectations, keep interaction controllable, make consequences clear, support correction, and provide global controls.
- Nielsen Norman Group, *10 Usability Heuristics*: visibility of system status, user control, error prevention, recognition, and recovery.
- W3C, *Web Content Accessibility Guidelines (WCAG) 2.2*: visible focus and target-size requirements, among other criteria.
- NIST, *AI Risk Management Framework* and *Generative AI Profile*: document risks, use appropriate measurement, and retain human oversight.
- Anthropic, *Demystifying evals for AI agents*: evaluate task outcomes and tool usage, include negative cases, and use explicit graders with inspected traces.

Links: https://www.microsoft.com/en-us/research/project/guidelines-for-human-ai-interaction/ ; https://www.nngroup.com/articles/ten-usability-heuristics/ ; https://www.w3.org/TR/WCAG22/ ; https://www.nist.gov/itl/ai-risk-management-framework ; https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
