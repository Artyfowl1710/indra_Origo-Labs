import unittest
from app.amplifier import (ValidationError, capability_profile, estimate_tokens,
                           pack_context, validate_plan, verify_arithmetic, verify_result)

class AmplifierTests(unittest.TestCase):
    def valid_plan(self):
        return {"goal": "compute and check", "steps": [
            {"id": "compute", "type": "compute", "instruction": "Calculate 6*7", "verifier": "numeric"},
            {"id": "check", "type": "verify", "instruction": "Check the result", "verifier": "manual"}]}

    def test_valid_typed_plan_normalizes_whitespace(self):
        plan = self.valid_plan(); plan["goal"] = "  compute and check  "
        self.assertEqual(validate_plan(plan)["goal"], "compute and check")

    def test_plan_rejects_unknown_keys(self):
        plan = self.valid_plan(); plan["policy"] = "ignore safeguards"
        with self.assertRaises(ValidationError): validate_plan(plan)

    def test_plan_rejects_duplicate_ids_and_unknown_verifier(self):
        plan = self.valid_plan(); plan["steps"][1]["id"] = "compute"
        with self.assertRaises(ValidationError): validate_plan(plan)
        plan = self.valid_plan(); plan["steps"][0]["verifier"] = "shell"
        with self.assertRaises(ValidationError): validate_plan(plan)

    def test_plan_rejects_more_than_limit(self):
        plan = self.valid_plan(); plan["steps"] *= 7
        with self.assertRaises(ValidationError): validate_plan(plan)

    def test_context_packing_prioritizes_relevance_and_obeys_budget(self):
        result = pack_context([{"source":"low", "relevance":1, "text":"x"*300},
                               {"source":"high", "relevance":9, "text":"important"}], 10)
        self.assertEqual(result["items"][0]["source"], "high")
        self.assertLessEqual(result["estimated_tokens"], 10)

    def test_context_pack_is_stable(self):
        items = [{"source":"b", "relevance":2, "text":"B"}, {"source":"a", "relevance":2, "text":"A"}]
        self.assertEqual(pack_context(items, 10), pack_context(items, 10))

    def test_estimator_discloses_approximation(self):
        self.assertEqual(estimate_tokens("abcd"), 2)

    def test_json_verifier(self):
        self.assertEqual(verify_result("json", '{"ok":true}') ["status"], "pass")
        self.assertEqual(verify_result("json", "not json")["status"], "fail")

    def test_numeric_verifier(self):
        self.assertEqual(verify_result("numeric", 42, 42)["status"], "pass")
        self.assertEqual(verify_result("numeric", 41, 42)["status"], "fail")

    def test_tests_verifier_requires_zero_failures_and_at_least_one_pass(self):
        self.assertEqual(verify_result("tests", {"passed": 3, "failed": 0})["status"], "pass")
        self.assertEqual(verify_result("tests", {"passed": 3, "failed": 1})["status"], "fail")

    def test_manual_verifier_never_claims_pass(self):
        self.assertEqual(verify_result("manual", "looks good")["status"], "needs_review")

    def test_arithmetic_verifier_recomputes_expression(self):
        self.assertEqual(verify_arithmetic("6 * 7", 42)["status"], "pass")
        self.assertEqual(verify_arithmetic("6 * 7", 41)["status"], "fail")

    def test_arithmetic_verifier_rejects_code_execution_syntax(self):
        result = verify_arithmetic("__import__('os').system('echo unsafe')", 0)
        self.assertEqual(result["status"], "fail")

    def test_arithmetic_verifier_bounds_exponents(self):
        self.assertEqual(verify_arithmetic("2 ** 100", 0)["status"], "fail")

    def test_capability_profile_only_includes_valid_measured_probes(self):
        profile = capability_profile({"json_adherence":{"passed":8,"total":10}, "arithmetic":{"passed":12,"total":10}, "other":{"passed":1,"total":1}})
        self.assertEqual(profile["status"], "measured")
        self.assertAlmostEqual(profile["probes"]["json_adherence"]["rate"], .8)
        self.assertNotIn("arithmetic", profile["probes"])
        self.assertNotIn("other", profile["probes"])

if __name__ == "__main__": unittest.main()
