"""Offline regression check for deterministic adaptive routing and budgets."""
import json, sys
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env', encoding='utf-8-sig')
from app.harness import choose_profile, budget_for_task

CASES = [
    ("quickly explain this function in two sentences", "fast"),
    ("debug and fix the failing tests", "deep"),
    ("review the architecture and benchmark performance", "deep"),
    ("help me plan my next task", "balanced"),
    ("define cosine similarity", "fast"),
]

def main():
    rows=[]
    for task, expected in CASES:
        actual=choose_profile(task); budget=budget_for_task(task)
        rows.append({"task":task,"expected":expected,"actual":actual,"correct":actual==expected,
                     "steps":budget.max_steps,"tool_calls":budget.max_tool_calls,"seconds":budget.max_duration_seconds})
    report={"suite":"deterministic-router-v1","cases":len(rows),"correct":sum(x['correct'] for x in rows),
            "accuracy":sum(x['correct'] for x in rows)/len(rows),"rows":rows}
    output=ROOT/'data'/'harness_eval.json'; output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2)); print(f"Saved: {output}")
    if report['accuracy'] < 1: raise SystemExit(1)
if __name__=='__main__': main()
