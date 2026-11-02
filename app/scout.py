"""Origo Scout: a bounded, read-only, no-inference self-test agent.

Scout checks the running app through its HTTP routes. It never sends a model
prompt, changes settings, writes files, approves actions, or reaches the network.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def run_scout(app: Any) -> dict[str, Any]:
    # Import lazily so normal app startup doesn't require the test client.
    from fastapi.testclient import TestClient

    checks: list[dict[str, Any]] = []

    def record(name: str, passed: bool, evidence: str, severity: str = "error") -> None:
        checks.append({
            "id": name.lower().replace(" ", "_"),
            "name": name,
            "status": "pass" if passed else ("warn" if severity == "warning" else "fail"),
            "severity": severity,
            "evidence": evidence[:240],
        })

    # No context manager: entering TestClient's lifespan would shut down the
    # live provider on exit. These read-only probes don't need startup hooks.
    client = TestClient(app, raise_server_exceptions=False)
    try:
        health = client.get("/api/health")
        health_data = health.json() if health.headers.get("content-type", "").startswith("application/json") else {}
        record("Health endpoint", health.status_code == 200 and health_data.get("ok") is True,
               f"HTTP {health.status_code}; ok={health_data.get('ok')}")

        home = client.get("/")
        csp = home.headers.get("content-security-policy", "")
        hardening = (home.status_code == 200
                     and home.headers.get("x-content-type-options") == "nosniff"
                     and "default-src 'self'" in csp
                     and "frame-ancestors 'none'" in csp)
        record("Browser security headers", hardening,
               f"HTTP {home.status_code}; nosniff={home.headers.get('x-content-type-options') == 'nosniff'}; CSP={'present' if csp else 'missing'}")

        status = client.get("/api/status")
        status_data = status.json() if status.status_code == 200 else {}
        safety = status_data.get("safety", {})
        expected_flags = ["workspace_scoped", "writes_require_approval", "secret_files_blocked", "symlinks_blocked"]
        flags_ok = status.status_code == 200 and status_data.get("app") == "Indra Origo" and all(safety.get(k) is True for k in expected_flags)
        record("Policy and workspace defaults", flags_ok,
               "Required policy flags: " + ", ".join(f"{k}={'on' if safety.get(k) is True else 'OFF'}" for k in expected_flags))
        record("OS-wide control remains gated", status.status_code == 200 and safety.get("desktop_control") is False,
               f"desktop_control={safety.get('desktop_control')}; direct OS automation is not enabled")

        capabilities = client.get("/api/capabilities")
        cap_data = capabilities.json() if capabilities.status_code == 200 else {}
        modalities = cap_data.get("modalities", {})
        modality_ok = capabilities.status_code == 200 and all(k in modalities for k in ("voice_input", "pdf_input", "image_input"))
        record("Modality inventory", modality_ok,
               f"HTTP {capabilities.status_code}; modalities={len(modalities)}; model-specific support stays separately labelled")

        profiles = client.get("/api/providers")
        profile_data = profiles.json() if profiles.status_code == 200 else {}
        profile_rows = profile_data.get("profiles", [])
        profile_ok = profiles.status_code == 200 and any(x.get("id") == "local" for x in profile_rows)
        # Report config state only. Never return endpoint auth material.
        record("Local provider profile", profile_ok,
               f"HTTP {profiles.status_code}; local_profile={'present' if profile_ok else 'missing'}; credentials are not inspected or emitted")

        scratch = client.get("/api/scratchpad")
        scratch_data = scratch.json() if scratch.status_code == 200 else {}
        scratch_ok = scratch.status_code == 200 and scratch_data.get("persistent") is True and "hidden" in scratch_data.get("purpose", "").lower()
        record("Inspectable scratchpad contract", scratch_ok,
               f"HTTP {scratch.status_code}; explicit-notes-only={scratch_data.get('persistent') is True}")

        sessions = client.get("/api/sessions")
        sessions_data = sessions.json() if sessions.status_code == 200 else None
        record("Conversation store read", sessions.status_code == 200 and isinstance(sessions_data, list),
               f"HTTP {sessions.status_code}; response_type={'list' if isinstance(sessions_data, list) else type(sessions_data).__name__}; contents omitted")

        amplifier = client.get("/api/amplifier/status")
        amp_data = amplifier.json() if amplifier.status_code == 200 else {}
        amp_ok = amplifier.status_code == 200 and isinstance(amp_data.get("features"), dict)
        record("Small-model amplifier routes", amp_ok,
               f"HTTP {amplifier.status_code}; feature_entries={len(amp_data.get('features', {})) if isinstance(amp_data.get('features'), dict) else 0}")

        extension = client.get("/api/extensions")
        ext_data = extension.json() if extension.status_code == 200 else {}
        ext_ok = extension.status_code == 200 and isinstance(ext_data.get("skills"), list) and isinstance(ext_data.get("plugins"), list)
        record("Extension registry is inspectable", ext_ok,
               f"HTTP {extension.status_code}; skills={len(ext_data.get('skills', []))}; plugins={len(ext_data.get('plugins', []))}")

        sandbox = client.get("/api/sandbox/status")
        sb_data = sandbox.json() if sandbox.status_code == 200 else {}
        network_disabled = sb_data.get("network_disabled_by_default") is True or sb_data.get("network_enabled") is False
        # Some sandbox statuses use a different schema; don't infer safety from absence.
        sb_ok = sandbox.status_code == 200 and isinstance(sb_data, dict)
        record("Sandbox status observable", sb_ok,
               f"HTTP {sandbox.status_code}; status fields={len(sb_data)}; network policy={'explicitly disabled' if network_disabled else 'inspect the sandbox status details'}",
               severity="error")

        pending = client.get("/api/permissions/pending")
        pending_data = pending.json() if pending.status_code == 200 else None
        pending_ok = pending.status_code == 200 and (isinstance(pending_data, list) or isinstance(pending_data, dict))
        record("Permission queue readable", pending_ok,
               f"HTTP {pending.status_code}; response shape={'valid' if pending_ok else 'unexpected'}; no permission was granted")
    except Exception as exc:  # Keep exception details minimal; no secrets or local paths.
        record("Scout probe runner", False, f"Probe runner raised {type(exc).__name__}")
    finally:
        client.close()

    failures = sum(1 for row in checks if row["status"] == "fail")
    warnings = sum(1 for row in checks if row["status"] == "warn")
    passed = sum(1 for row in checks if row["status"] == "pass")
    return {
        "agent": "Origo Scout",
        "version": "1.0",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if failures == 0 and warnings == 0 else "review" if failures == 0 else "fail",
        "summary": {"total": len(checks), "passed": passed, "warnings": warnings, "failed": failures},
        "safety_contract": {
            "model_inference": False,
            "outbound_network": False,
            "writes": False,
            "settings_changed": False,
            "approvals_granted": False,
            "scope": "bounded read-only application HTTP probes",
        },
        "checks": checks,
    }
