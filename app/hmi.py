"""Deterministic heuristic audit for Origo's own human-machine interface.

This is a static checklist, not a substitute for usability studies, assistive-
technology testing, color-contrast measurement, or a formal WCAG conformance claim.
It reads only the local frontend source files and performs no network or writes.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


DARK_PATTERN = re.compile(
    r"\b(?:last chance|limited time offer|act now|only \d+ left|you(?:'|’)ll lose|"
    r"don't miss out|do not miss out|keep your streak alive|don't leave me|you need me|i miss you|come back now|you owe me)\b",
    re.IGNORECASE,
)


def _check(check_id: str, name: str, passed: bool, evidence: str,
           severity: str = "error", category: str = "usability") -> dict[str, str]:
    return {
        "id": check_id,
        "name": name,
        "status": "pass" if passed else ("warn" if severity == "warning" else "fail"),
        "severity": severity,
        "category": category,
        "evidence": evidence[:220],
    }


def _hex_luminance(value: str) -> float | None:
    """Return WCAG relative luminance for a 3/6-digit hex token."""
    raw = value.lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", raw):
        return None
    channels = [int(raw[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in channels]
    return sum(channel * weight for channel, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def _contrast_ratio(foreground: str, background: str) -> float | None:
    a, b = _hex_luminance(foreground), _hex_luminance(background)
    if a is None or b is None:
        return None
    light, dark = max(a, b), min(a, b)
    return (light + 0.05) / (dark + 0.05)


def audit_sources(html: str, css: str, js: str, policy_source: str = "") -> dict[str, Any]:
    """Evaluate a small, explainable set of testable HMI heuristics."""
    checks: list[dict[str, str]] = []
    title_match = re.search(r"<title>\s*([^<]+?)\s*</title>", html, re.IGNORECASE)
    language_declared = bool(re.search(r"<html\b[^>]*\blang\s*=\s*['\"][a-zA-Z-]+['\"]", html, re.I))
    checks.append(_check(
        "document_identity", "Page language and title",
        language_declared and bool(title_match and title_match.group(1).strip()),
        f"language={'declared' if language_declared else 'missing'}; title={'present' if title_match else 'missing'}",
        category="accessibility",
    ))
    tokens = {name: value for name, value in re.findall(r"--([a-zA-Z0-9_-]+)\s*:\s*(#[0-9a-fA-F]{3,6})\b", css)}
    contrast_pairs = [("text", "bg"), ("muted", "bg"), ("accent", "bg"), ("red", "bg"), ("yellow", "bg")]
    contrast_results = []
    for foreground, background in contrast_pairs:
        if foreground in tokens and background in tokens:
            ratio = _contrast_ratio(tokens[foreground], tokens[background])
            contrast_results.append((foreground, background, ratio))
    contrast_ok = len(contrast_results) == len(contrast_pairs) and all(ratio is not None and ratio >= 4.5 for _, _, ratio in contrast_results)
    contrast_evidence = "; ".join(f"{fg}/{bg}={ratio:.2f}:1" if ratio is not None else f"{fg}/{bg}=unavailable" for fg, bg, ratio in contrast_results)
    checks.append(_check(
        "core_token_contrast", "Core text/status color tokens meet 4.5:1 contrast target",
        contrast_ok,
        (contrast_evidence or "Could not find expected color tokens") + "; checks source tokens only, not every rendered component.",
        category="accessibility",
    ))
    checks.append(_check(
        "visible_focus", "Keyboard focus indicator",
        bool(re.search(r":focus-visible\s*\{[^}]*outline\s*:\s*[^;}]+", css, re.I | re.S)),
        "A :focus-visible outline rule is present." if ":focus-visible" in css else "No :focus-visible selector found.",
        category="accessibility",
    ))
    checks.append(_check(
        "reduced_motion", "Reduced-motion preference",
        bool(re.search(r"prefers-reduced-motion\s*:\s*reduce", css, re.I)),
        "Reduced-motion media query is present." if "prefers-reduced-motion:reduce" in css.replace(" ", "") else "No reduced-motion media query found.",
        category="accessibility",
    ))
    checks.append(_check(
        "live_feedback", "Announced status feedback",
        bool(re.search(r"aria-live\s*=\s*['\"]polite['\"]", html, re.I))
        and bool(re.search(r"role\s*=\s*['\"]status['\"]", html, re.I)),
        "Polite live regions and status roles are present." if "aria-live" in html and "role=\"status\"" in html else "Check long-running/action feedback for screen-reader announcements.",
        category="accessibility",
    ))
    checks.append(_check(
        "command_palette", "Discoverable keyboard command palette",
        "command-palette" in html and "command-palette" in css and "command-palette" in js
        and bool(re.search(r"event\.key\.toLowerCase\(\)\s*===\s*['\"]k['\"]", js))
        and bool(re.search(r"event\.key\s*===\s*['\"]Escape['\"]", js)),
        "Command palette markup/styles and Ctrl/Command+K plus Escape handling found." if "command-palette" in html and "command-palette" in js else "Missing command-palette markup or keyboard handling.",
        category="efficiency",
    ))
    message_labeled = bool(re.search(r"<label[^>]*for=['\"]message['\"]", html, re.I))
    command_search_labeled = bool(re.search(r"<label[^>]*for=['\"]command-palette-search['\"]", html, re.I))
    checks.append(_check(
        "input_labels", "Primary and command inputs have labels",
        message_labeled and command_search_labeled,
        f"composer_label={'present' if message_labeled else 'missing'}; command_search_label={'present' if command_search_labeled else 'missing'}",
        category="accessibility",
    ))
    approval_boundary = "permission-modal" in html and "Approve once" in html and "writes_require_approval" in policy_source
    checks.append(_check(
        "consequential_action_review", "Consequential actions expose an approval boundary",
        approval_boundary,
        "Approval dialog and approval-first write contract are visible in source." if approval_boundary else "Could not find both the approval dialog and approval-first write contract.",
        category="safety",
    ))
    checks.append(_check(
        "reminder_control", "Companion reminders are optional and snoozable",
        'id="ori-reminders"' in html and "ori-later" in html and "oriEnabled" in js and "oriSnoozeUntil" in js,
        "A persistent opt-out control and snooze state are present." if 'id="ori-reminders"' in html and "oriSnoozeUntil" in js else "Companion reminder opt-out/snooze control is incomplete.",
        category="agency",
    ))
    autoplay = bool(re.search(r"<(?:audio|video)\b[^>]*\bautoplay\b", html, re.I))
    unprompted_play = bool(re.search(r"\.(?:play|speak)\s*\(\s*\)", js)) and not bool(re.search(r"voice-output[^\n]{0,200}checked", js))
    checks.append(_check(
        "no_autoplay_media", "No unrequested autoplay media",
        not autoplay and not unprompted_play,
        "No media autoplay attribute or obvious unconditional play/speak call found." if not autoplay and not unprompted_play else "Review autoplay or automatic audio playback; motion/audio can surprise users.",
        severity="error", category="agency",
    ))
    dark_patterns = DARK_PATTERN.findall(html + "\n" + js)
    checks.append(_check(
        "no_manipulative_urgency", "No obvious scarcity/urgency dark-pattern copy",
        not bool(dark_patterns),
        "No targeted urgency/scarcity phrases found." if not dark_patterns else "Review potentially manipulative copy: " + ", ".join(sorted(set(dark_patterns))[:3]),
        category="ethics",
    ))
    cancel_visible = bool(re.search(r"id=['\"]cancel['\"][^>]*", html, re.I)) and "Cancel run" in html
    checks.append(_check(
        "cancel_long_tasks", "Long-running tasks have a visible cancel route",
        cancel_visible and "activeController?.abort()" in js,
        "Cancel control and abort handling found." if cancel_visible and "activeController?.abort()" in js else "Could not verify a visible cancel path for active runs.",
        category="user_control",
    ))
    suggestions_match = re.search(r"<div class=\"suggestions\"[^>]*>(.*?)</div>\s*<div id=\"conversation\"", html, re.I | re.S)
    suggestion_count = len(re.findall(r"data-prompt=", suggestions_match.group(1))) if suggestions_match else 0
    checks.append(_check(
        "starter_choice_density", "Starter surface offers a bounded set of quick-start choices",
        3 <= suggestion_count <= 8,
        f"Detected {suggestion_count} visible quick-start prompts; this is a maintainability heuristic, not a universal cognitive limit.",
        severity="warning", category="cognitive_load",
    ))
    error_recovery = "Open Diagnostics" in js and "REQUEST FAILED" in js
    checks.append(_check(
        "actionable_errors", "Errors direct users toward recovery",
        error_recovery,
        "Request failures offer diagnostics/log recovery guidance." if error_recovery else "Could not find explicit error-recovery guidance.",
        severity="warning", category="recovery",
    ))
    local_transparency = "LOCAL-FIRST" in html.upper() and "Uploaded files are sent only when attached" in html
    checks.append(_check(
        "data_transparency", "Local-first and attachment data flow are disclosed",
        local_transparency,
        "UI discloses local-first intent and attachment submission behavior." if local_transparency else "Review whether local/remote data paths are explained in context.",
        severity="warning", category="trust",
    ))
    capsule_scope = (
        "Only the workspace-relative files you explicitly list" in html
        and "never executes archived code" in html
        and "signer_fingerprint_sha256" in (Path(__file__).parent / "evidence.py").read_text(encoding="utf-8")
    )
    checks.append(_check(
        "capsule_scope_transparency", "Capsule scope, verification and non-execution are explicit",
        capsule_scope,
        "UI explains explicit file selection and passive verification." if capsule_scope else "Explain what a Capsule includes and make clear that verification never executes its contents.",
        category="trust",
    ))
    proof_honesty = "Numeric matching is only lexical" in html and "not proof of truth" in html and "does not automatically find every factual claim" in html and "not yet wired into every exporter" in html
    checks.append(_check(
        "proof_ledger_honesty", "Evidence attachment is not misrepresented as automatic truth verification",
        proof_honesty,
        "The user-facing Proof Ledger states its limitations." if proof_honesty else "Clarify that linked evidence and numeric-token matching do not establish truth or semantic entailment.",
        category="trust",
    ))
    frontend_bundle = html + "\n" + js
    grandiosity = re.search(r"\b(?:perfect accuracy|100% accurate|always correct|never makes mistakes|human-level intelligence|trust me completely|fully autonomous)\b", frontend_bundle, re.I)
    checks.append(_check(
        "no_unsubstantiated_ai_claims", "No absolute or unsupported AI capability promises",
        not bool(grandiosity),
        "No targeted absolute-capability claims found." if not grandiosity else "Review potentially misleading product promise: " + grandiosity.group(0),
        category="trust",
    ))
    agency_contract = '"desktop_control": False' in policy_source and "writes_require_approval" in policy_source and "Deny" in html and "Approve once" in html
    checks.append(_check(
        "agent_agency_boundary", "Agent actions retain explicit deny/approve controls and no desktop-control claim",
        agency_contract,
        "Current contract shows desktop control disabled and writes approval-gated." if agency_contract else "Recheck that consequential actions preserve denial, per-action approval and explicit desktop-control status.",
        category="agency",
    ))
    voice_disclosure = "recognition may use your browser vendor's service" in html.lower() or "may use a browser-vendor service" in html.lower()
    checks.append(_check(
        "voice_data_flow_disclosure", "Voice input explains browser-vendor processing uncertainty",
        voice_disclosure,
        "Voice UI notes that recognition may depend on browser-vendor processing." if voice_disclosure else "Disclose that browser speech recognition is not guaranteed to be offline.",
        category="privacy",
    ))
    undo_recovery = "undo" in frontend_bundle.lower() and "Cancel run" in html
    checks.append(_check(
        "undo_and_cancel_recovery", "Users have visible cancellation and undo/recovery affordances",
        undo_recovery,
        "Cancel and undo/recovery routes are present in the UI bundle." if undo_recovery else "Expose cancellation and recovery for long-running or consequential actions.",
        severity="warning", category="recovery",
    ))
    calibrated_notice = (
        "renderAnswerTrustNote" in js
        and "do not guarantee correctness" in js.lower()
        and "linked evidence" in js.lower()
    )
    checks.append(_check(
        "calibrated_output_notice", "Generated answers carry a non-alarmist correctness caveat",
        calibrated_notice,
        "Run-linked answers distinguish inspectable traces/evidence from a correctness guarantee." if calibrated_notice else "Set expectations that model text and trace/evidence artifacts are not themselves a guarantee of correctness.",
        severity="warning", category="trust",
    ))
    feedback_present = (
        "renderRunFeedback" in js and "saveRunFeedback" in js and "No rating is required to use Origo" in html + js
        and 'id="feedback-clear"' in html
    )
    checks.append(_check(
        "optional_outcome_feedback", "Outcome ratings are optional, editable and clearable",
        feedback_present,
        "Per-answer ratings can be changed/removed, and the dashboard provides a clear-all control." if feedback_present else "Make feedback optional; support corrections/removal and a clear-all route.",
        category="agency",
    ))
    feedback_privacy = (
        "not sent to the model" in (html + "\n" + js).lower()
        and "used for training" in (html + "\n" + js).lower()
        and '"local_only": True' in (Path(__file__).parent / "store.py").read_text(encoding="utf-8")
        and "automatic_adaptation" in (Path(__file__).parent / "store.py").read_text(encoding="utf-8")
    )
    checks.append(_check(
        "outcome_feedback_privacy", "Feedback data flow and limits are disclosed",
        feedback_privacy,
        "Ratings are disclosed as local-only signals, not model inputs, training data, or automatic adaptation." if feedback_privacy else "Disclose where ratings are stored and whether they affect models or behavior.",
        category="privacy",
    ))
    fails = sum(x["status"] == "fail" for x in checks)
    warns = sum(x["status"] == "warn" for x in checks)
    passed = sum(x["status"] == "pass" for x in checks)
    return {
        "audit": "Indra Origo HMI Quality Gate",
        "version": "1.2",
        "status": "fail" if fails else "review" if warns else "pass",
        "scope": "deterministic static heuristics; not a usability study or WCAG conformance certification",
        "summary": {"total": len(checks), "passed": passed, "warnings": warns, "failed": fails},
        "checks": checks,
        "limitations": [
            "Contrast checks cover core CSS tokens only; component-level combinations and gradients may differ.",
            "Does not measure target-size geometry after browser rendering.",
            "Does not test keyboard navigation with a real browser or screen reader.",
            "Passing checks do not demonstrate that users find the interface usable; conduct moderated usability tests.",
        ],
    }


def audit_frontend(static_dir: Path | str) -> dict[str, Any]:
    root = Path(static_dir)
    html_path, css_path, js_path = root / "index.html", root / "style.css", root / "app.js"
    missing = [p.name for p in (html_path, css_path, js_path) if not p.is_file()]
    if missing:
        return {
            "audit": "Indra Origo HMI Quality Gate", "version": "1.2", "status": "fail",
            "scope": "deterministic static heuristics; not a usability study or WCAG conformance certification",
            "summary": {"total": 1, "passed": 0, "warnings": 0, "failed": 1},
            "checks": [_check("frontend_files", "Frontend source files exist", False, "Missing: " + ", ".join(missing))],
            "limitations": ["HMI evaluation did not run because required frontend files are missing."],
        }
    return audit_sources(html_path.read_text(encoding="utf-8"), css_path.read_text(encoding="utf-8"), js_path.read_text(encoding="utf-8"), (root.parent / "main.py").read_text(encoding="utf-8"))
