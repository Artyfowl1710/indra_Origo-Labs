import json
import unittest
from app.harness import RunBudget, RunState

class FakeStore:
    def __init__(self): self.events=[]
    def event(self, kind, **fields):
        row={"type":kind, **fields}; self.events.append(row); return row

class HarnessTests(unittest.TestCase):
    def test_state_transitions_are_checked_and_logged(self):
        store=FakeStore(); state=RunState("r1", store)
        state.transition("running")
        state.transition("completed")
        self.assertEqual(state.status, "completed")
        self.assertEqual([x["type"] for x in store.events], ["run_state_changed", "run_state_changed"])
        with self.assertRaises(ValueError): state.transition("running")

    def test_tool_result_budget_truncates_large_results(self):
        budget=RunBudget(max_result_chars=500)
        result=budget.clip_result({"content":"x"*2000})
        self.assertTrue(result["truncated"])
        self.assertLessEqual(len(json.dumps(result)), 700)

    def test_small_results_are_unchanged(self):
        budget=RunBudget(max_result_chars=500)
        self.assertEqual(budget.clip_result({"ok":True}), {"ok":True})

if __name__ == "__main__": unittest.main()
