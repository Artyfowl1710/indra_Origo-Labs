# Indra Origo: hackathon demo playbook

## The story to tell

**“Most AI demos show what the agent can do. Origo shows what it did, what evidence exists, what it cannot guarantee, and how the human stays in control.”**

Do not pitch Origo as a fully autonomous superintelligence or a replacement operating system kernel. Pitch it as a local-first intelligence workbench with an explicit policy boundary and inspectable run artifacts. Judges can verify the smaller promise on screen.

## Hero demo: the agent that leaves evidence and respects a no

Rehearse a single, deterministic workflow end-to-end before adding any optional feature. Keep a clean disposable project and do not use real private files.

| Time | What the judge sees | What it demonstrates | What not to claim |
|---|---|---|---|
| 0:00–0:15 | Open with a sample confidential engineering/research task and the problem of opaque AI changes | Clear use case and stakes | Do not claim regulatory certification or absolute privacy |
| 0:15–0:35 | Show local model/provider configuration and the policy/permission surface | The inference path and capabilities are inspectable | Say “local-first” only when the selected provider actually runs locally; don't call the app air-gapped unless network isolation was independently demonstrated |
| 0:35–1:05 | Ask for a small workspace change; inspect the exact diff; reject it | A capable assistant can propose work without taking away user agency | Don't fake the model call or hide failed runs |
| 1:05–1:35 | Approve a separate harmless change in the disposable project, then show the backup/undo route | Review, execution and recovery are connected | Don't overwrite a real user file during a demo |
| 1:35–2:05 | Create a Capsule from selected safe files; verify the manifest and signer fingerprint | Integrity and inspectable artifact provenance | A valid signature establishes integrity under a key, not truth or signer identity without a trusted fingerprint |
| 2:05–2:30 | Verify a copied Capsule after altering one copied payload byte | Tampering is observable | Never corrupt the original artifact or present a scripted screenshot as a live verification |
| 2:30–2:50 | Show Proof Ledger findings for a mismatched or stale claim | The system can flag an evidence problem instead of silently blessing it | A lexical match is not semantic truth checking; disclose the current scope |
| 2:50–3:10 | Show the HMI Gate, per-answer correctness caveat, and optional rating summary | Trust calibration, accessibility guardrails and user feedback | 24 static checks are not a user study or WCAG certification |
| 3:10–3:20 | Close on the integrity receipt/run evidence | The product’s differentiator is inspectability plus human control | No promises of perfect accuracy or guaranteed award wins |

The exact timing is a rehearsal target, not a claim that every model/provider will finish within a fixed time. If a live model is slow, prepare a second run against a known working local model and disclose when any artifact was prepared earlier.

## A scorecard for judging categories

Use the event's actual published rubric. In the absence of a specific rubric, prepare evidence for these common dimensions:

- **Problem fit/productivity:** timed task against a manual baseline using the same sample project. Report elapsed time, errors, and human interventions across at least several repetitions; do not estimate savings after one run.
- **Technical depth:** show the policy broker, typed tool surface, signed Capsule manifest, evidence hash/freshness check, and negative tests. Keep the architecture diagram consistent with what actually ships.
- **Responsible AI/security:** demonstrate an explicit denial, a no-side-effect rejected proposal, stale-overwrite rejection, and a tamper-detection case. Distinguish implemented boundaries from future Windows hardening.
- **User experience/accessibility:** keyboard-first command palette, visible status/cancel/recovery, readable diffs, reduced-motion support, optional ratings, and a real keyboard-only walk-through. The static HMI gate is supporting evidence, not the whole proof.
- **Use of AI:** show a real run through the configured model, then identify which checks are deterministic tools versus model-generated judgments.
- **Impact/adoption:** explain the first user segment (labs, engineers, or confidential knowledge workers) and a concrete workflow. Don't pitch all possible markets at equal depth.

For each scorecard item, capture one artifact: a live screen, a test output, a benchmark table, a threat-model note, or a short user observation. A feature list without evidence is a weak submission.

## A credible public/viral hook

The most shareable moment is an honest, visual challenge: **“Can you alter one file inside this AI run's exported Capsule and still pass verification?”** Show the original passing, modify only a disposable copy, and show the modified copy failing verification. Then explain the limitation: integrity checks do not prove scientific truth. This is memorable because it is falsifiable, not because it uses urgency or anthropomorphic pressure.

Turn the result into a short clip only after recording the workflow live. Keep real files, API keys, workspace names, private prompts, local paths, signer secrets and model credentials out of frame. A companion character may be warm, but do not make it guilt-trip users or imply it suffers when dismissed.

## Pre-demo checklist

- [ ] Fresh project checkout / clean disposable workspace; no personal database or signing key in the distributable ZIP.
- [ ] `python -m unittest discover -s tests -q` passes on the exact package.
- [ ] `python scripts/validate_extensions.py` passes; disabled plugins remain disabled.
- [ ] HMI Gate has no unexpected findings; disclose its static scope.
- [ ] Local model inference and tool calling were actually smoke-tested on the machine used for the demo.
- [ ] Rehearse rejected and approved file proposals, undo, Capsule creation/verification, and tamper detection.
- [ ] Run at 100% and 150–200% zoom; keyboard-only navigation; reduced-motion setting; 390px narrow viewport; no overflow.
- [ ] Prepare a fallback recording, labelled as a recording, but keep a live path ready.
- [ ] Ask a first-time user to perform the core task without coaching; fix blockers before polishing animations.
- [ ] Remove private data from screenshots and exports; confirm no unexpected network egress before calling the demo local-only.

## What will improve the odds more than another feature

A consistent end-to-end demo, one measured productivity comparison, a clean visual hierarchy, and evidence for each security claim will generally be more persuasive than implementing more disconnected agents. Choose award categories according to the published criteria and optimize a strong primary submission first; no design can guarantee winning every track.
