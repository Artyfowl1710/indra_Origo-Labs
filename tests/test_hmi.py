import os
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

import app.main as main_module
from app.hmi import audit_sources, audit_frontend
from app.store import Store

PROJECT = Path(__file__).resolve().parents[1]


class HmiQualityGateTests(unittest.TestCase):
    def test_current_frontend_passes_static_gate(self):
        report = audit_frontend(PROJECT / "app" / "static")
        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertGreaterEqual(report["summary"]["total"], 12)
        self.assertTrue(all(check["status"] == "pass" for check in report["checks"]))
        self.assertIn("not a usability study", report["scope"])

    def test_low_contrast_design_tokens_fail_contrast_guardrail(self):
        html = '<html lang="en"><head><title>Test</title></head><body></body></html>'
        css = ':root{--bg:#ffffff;--text:#eeeeee;--muted:#dddddd;--accent:#eeeeee;--red:#eeeeee;--yellow:#eeeeee}:focus-visible{outline:2px solid black}@media(prefers-reduced-motion:reduce){*{animation:none}}'
        js = ""
        report = audit_sources(html, css, js)
        contrast = next(item for item in report["checks"] if item["id"] == "core_token_contrast")
        self.assertEqual(contrast["status"], "fail")
        self.assertIn("text/bg=", contrast["evidence"])

    def test_flags_accessibility_and_escape_route_regressions(self):
        html = '<html><head><title>Test</title></head><body><textarea id="message"></textarea></body></html>'
        css = "body { color: black; }"
        js = "function run() {}"
        report = audit_sources(html, css, js, policy_source="")
        by_id = {item["id"]: item for item in report["checks"]}
        for check_id in ("document_identity", "visible_focus", "reduced_motion", "command_palette", "input_labels", "cancel_long_tasks"):
            self.assertEqual(by_id[check_id]["status"], "fail", check_id)

    def test_flags_autoplay_and_manipulative_urgency_copy(self):
        html = '''<html lang="en"><head><title>Test</title></head><body>
        <label for="message">Message</label><textarea id="message"></textarea>
        <video autoplay></video><p>Last chance: act now, only 2 left!</p>
        <div id="permission-modal">Approve once</div>
        <label for="command-palette-search">Search commands</label><input id="command-palette-search">
        </body></html>'''
        css = ':focus-visible { outline: 2px solid white; } @media (prefers-reduced-motion: reduce) { * { animation: none; } }'
        js = "event.key.toLowerCase() === 'k'; event.key === 'Escape'; command-palette; activeController?.abort();"
        report = audit_sources(html, css, js, policy_source="writes_require_approval")
        by_id = {item["id"]: item for item in report["checks"]}
        self.assertEqual(by_id["no_autoplay_media"]["status"], "fail")
        self.assertEqual(by_id["no_manipulative_urgency"]["status"], "fail")

    def test_research_provenance_limits_are_disclosed(self):
        html = (PROJECT / "app/static/index.html").read_text(encoding="utf-8")
        self.assertIn("Only the workspace-relative files you explicitly list", html)
        self.assertIn("never executes archived code", html)
        self.assertIn("not proof of truth", html)
        self.assertIn("recognition may use your browser vendor's service", html)

    def test_flags_unsubstantiated_ai_grandiosity_and_guilt_copy(self):
        html = """<html lang="en"><head><title>Test</title></head><body><p>Fully autonomous, perfect accuracy.</p><p>Don't leave me; keep your streak alive.</p></body></html>"""
        css = ':root{--bg:#000000;--text:#ffffff;--muted:#eeeeee;--accent:#ffffff;--red:#ffffff;--yellow:#ffffff}:focus-visible{outline:2px solid white}@media(prefers-reduced-motion:reduce){*{animation:none}}'
        js = "event.key.toLowerCase() === 'k'; event.key === 'Escape'; command-palette; activeController?.abort();"
        report = audit_sources(html, css, js, policy_source='writes_require_approval')
        by_id = {item["id"]: item for item in report["checks"]}
        self.assertEqual(by_id["no_unsubstantiated_ai_claims"]["status"], "fail")
        self.assertEqual(by_id["no_manipulative_urgency"]["status"], "fail")

    def test_outcome_feedback_is_optional_and_privacy_disclosed(self):
        html = (PROJECT / "app/static/index.html").read_text(encoding="utf-8")
        css = (PROJECT / "app/static/style.css").read_text(encoding="utf-8")
        js = (PROJECT / "app/static/app.js").read_text(encoding="utf-8")
        policy = (PROJECT / "app/main.py").read_text(encoding="utf-8")
        report = audit_sources(html, css, js, policy_source=policy)
        by_id = {item["id"]: item for item in report["checks"]}
        self.assertEqual(by_id["optional_outcome_feedback"]["status"], "pass")
        self.assertEqual(by_id["outcome_feedback_privacy"]["status"], "pass")
        self.assertEqual(by_id["calibrated_output_notice"]["status"], "pass")
        # A variant that hides the optionality disclosure must not pass the HMI gate.
        stripped = html.replace("No rating is required to use Origo.", "Rate every answer before continuing.")
        stripped_js = js.replace("No rating is required to use Origo.", "Rate every answer before continuing.")
        bad = audit_sources(stripped, css, stripped_js, policy_source=policy)
        bad_by_id = {item["id"]: item for item in bad["checks"]}
        self.assertEqual(bad_by_id["optional_outcome_feedback"]["status"], "fail")

    def test_hmi_audit_route_is_read_only_report(self):
        old_store = main_module.store
        old_data_dir = os.environ.get("INDRA_DATA_DIR")
        with tempfile.TemporaryDirectory() as temp:
            os.environ["INDRA_DATA_DIR"] = temp
            main_module.store = Store()
            try:
                with TestClient(main_module.app) as client:
                    response = client.get("/api/hmi/audit")
                self.assertEqual(response.status_code, 200, response.text)
                report = response.json()
                self.assertEqual(report["status"], "pass", report)
                self.assertEqual(report["summary"]["failed"], 0)
                self.assertEqual(report["audit"], "Indra Origo HMI Quality Gate")
            finally:
                main_module.store = old_store
                if old_data_dir is None:
                    os.environ.pop("INDRA_DATA_DIR", None)
                else:
                    os.environ["INDRA_DATA_DIR"] = old_data_dir

    def test_command_palette_has_label_shortcut_escape_and_visible_opener(self):
        html = (PROJECT / "app/static/index.html").read_text(encoding="utf-8")
        js = (PROJECT / "app/static/app.js").read_text(encoding="utf-8")
        self.assertIn('id="command-palette-open"', html)
        self.assertIn('for="command-palette-search"', html)
        self.assertIn('aria-modal="true"', html)
        self.assertIn("openCommandPalette()", js)
        self.assertIn("closeCommandPalette()", js)
        self.assertIn("toggleFocusMode()", js)


if __name__ == "__main__":
    unittest.main()
