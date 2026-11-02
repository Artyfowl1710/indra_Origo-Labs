# HMI, psychology, and trust guardrails

## Product stance

Origo should help people exercise agency, not maximize time-on-app. Good engagement means returning because the workbench reliably helps users do meaningful work—not because it uses streak anxiety, fake urgency, guilt, or notification pressure.

## Rules we want in the product

1. **Make state visible.** Show which provider/profile is selected, whether a run is active, what it used, what is pending, and whether a result is verified. Long operations need progress and a cancel path.
2. **Preserve user control.** Make Escape/Cancel/close behavior predictable, allow users to leave a flow, and make consequential actions reviewable. A selection in the command palette navigates or prepares work; it does not bypass established confirmation or approval gates.
3. **Prefer recognition to recall.** Provide searchable commands, plain-language labels, visible shortcuts, and saved context the user can inspect rather than requiring memorized commands or hidden memory.
4. **Reduce avoidable cognitive load.** Keep the default start surface bounded. Reveal advanced controls in the relevant workspace, not all at once. Focus mode reduces chrome without removing a route back to navigation.
5. **Respect sensory preferences.** Honor `prefers-reduced-motion`; never autoplay audio/video; keep voice output user-enabled; allow companion reminders to be snoozed or disabled.
6. **Prevent errors before explaining them.** Keep file writes, network actions, external sends, payments, and OS control behind previews/permission boundaries. Clearly distinguish “drafted”, “proposed”, “approved”, and “completed”.
7. **Make recovery useful.** Use readable error messages and direct people to a safe next step. Keep undo where the action can be reversed, and preserve evidence for consequential operations.
8. **Do not manipulate.** No fake scarcity, countdowns, guilt-inducing reminders, dark-pattern opt-outs, streak pressure, or deceptive “thinking”/progress indicators.
9. **Be privacy-legible.** Separate local processing from hosted inference; show when files leave the device; do not silently inject the project scratchpad into prompts; don't use personal data to infer a user's emotional state without a clearly explained feature and consent.
10. **Measure usability with users.** A static audit can check source-level affordances, but cannot prove that a person understands them. Validate with tasks, observation, error rates, completion time, and short post-task confidence/usability prompts.

## Shipped in v1.4–v1.6

- Searchable keyboard-first command palette (Ctrl/Command+K, Escape to close, arrow-key selection, focus containment and return to the opener).
- Focus mode to hide navigation chrome, with a keyboard route back through the command palette.
- Read-only HMI Quality Gate API and Diagnostics UI: language/title, focus indicator, reduced motion, core token contrast, live feedback, labelled inputs, keyboard palette, approval boundary, optional/snoozable companion reminders, no autoplay, no obvious scarcity/urgency copy, cancel path, bounded quick-start choices, error recovery, and data-flow disclosure.
- Regression fixtures that deliberately remove affordances, lower contrast, add autoplay, add manipulative urgency/guilt copy, remove outcome-rating optionality, and make unsupported capability promises; tests assert the audit catches them.
- v1.5 provenance UI with explicit Capsule file selection, visible signing fingerprints, evidence excerpts, stale-source checks, and clear limits on claim verification.
- v1.6 per-answer correctness caveat plus optional outcome ratings with edit/remove/clear controls, local-only data-flow disclosure, and tests that feedback does not call the model or store prompt/answer text.

## v1.5 HMI rule set and release gates

The HMI Quality Gate contains 24 explainable source-level checks. It covers document identity, focus indicators, reduced motion, selected contrast tokens, live status feedback, keyboard command discovery, input labels, consequential-action approval boundaries, optional/snoozable companion reminders, autoplay, urgency/guilt language, cancellation, bounded starter-choice density, actionable errors, data-flow disclosure, Capsule scope, Proof Ledger caveats, absolute capability promises, agent permission boundaries, browser voice processing disclosure, undo/recovery affordances, a calibrated generated-answer caveat, optional/clearable outcome ratings, and rating data-flow transparency.

The next level of testing must use realistic tasks, not only source inspection. Suggested pilot tasks:

1. Ask Origo to modify a file, inspect its diff, reject it, and confirm the target file is unchanged.
2. Create a Capsule, alter one payload file in a copy, and confirm verification fails. Have another person verify a signed Capsule while checking its signer fingerprint independently.
3. Register a claim whose number differs from the evidence, modify the evidence source, and confirm the ledger flags both mismatch and staleness.
4. Use the full core flow by keyboard only, escape a modal, return focus to its trigger, and cancel an active request.
5. Disable Ori reminders, wait through a focus session, and verify no nudge returns; enable reduced-motion mode and confirm nonessential animation stops.
6. Attach an image with forwarding disabled, submit without attachment permission, and verify the provider payload excludes image bytes.

For the first moderated pilot, recruit at least 5–8 people across researcher, engineer and student workflows; this is formative testing, not a statistically powered experiment. Track critical-task completion, wrong-action rate, recovery time, observed confusion, accessibility blockers and a short post-task confidence score. Fix every critical safety/accessibility blocker before expanding connector autonomy. Once the interface stabilizes, compare variants with pre-registered hypotheses and task-level success metrics rather than optimizing click-through or session length.

### Anti-patterns that are out of scope by design

- Streaks, fake scarcity, countdowns, guilt prompts, manipulative notifications, friction-heavy opt-outs and endless engagement loops.
- Companion behavior that implies it has feelings, suffers when dismissed, or needs the user to return. Ori may be warm, but it must make its nature and controls clear.
- “100% accurate”, “always correct”, “fully autonomous” or other unsupported claims about model quality.
- Silent upload of project context, hidden memory injection, unlabeled network egress, or use of a hosted provider without showing the selected profile.
- Auto-send, auto-purchase, destructive host actions, global computer-control permissions or long-running background actions without explicit per-capability consent, receipts and recovery.
- Fake progress percentages or “verified” labels inferred only from a model's confident text. Use measurable status states: queued, running, waiting for approval, completed, failed, cancelled, and verified by a named check.

## What the audit does not claim

The HMI Quality Gate is a deterministic static heuristic, not a formal WCAG conformance report, clinical psychology assessment, or proof of usability. Its color test covers a small set of source CSS tokens—not every component, opacity, gradient, or rendered state. It does not measure target dimensions in-browser or exercise a real screen reader. Actual usability testing and browser/assistive-technology testing remain release gates.

## References

- Nielsen Norman Group, [10 Usability Heuristics for User Interface Design](https://www.nngroup.com/articles/ten-usability-heuristics/): visibility of status, user control, error prevention, recognition over recall, efficiency, and recovery.
- W3C, [Web Content Accessibility Guidelines (WCAG) 2.2](https://www.w3.org/TR/WCAG22/): focus visibility, target sizing, consistent help, and accessibility criteria. The token check here is not a WCAG conformance claim.
- Microsoft Research, [Guidelines for Human-AI Interaction](https://www.microsoft.com/en-us/research/project/guidelines-for-human-ai-interaction/): validated recommendations covering expectation setting, context-sensitive behavior, correction/dismissal, explanations, global controls and cautious adaptation.
- NIST, [AI Risk Management Framework — Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/): Govern, Map, Measure and Manage as a continuous risk-management frame for system design and testing.
- MIT, [Heuristic Evaluation and User-Centered Design](https://designftw.csail.mit.edu/lectures/heuristic-eval/): evaluation as a way to identify and justify interface problems.
