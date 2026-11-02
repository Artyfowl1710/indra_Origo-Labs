"""Protected recording acceptance check. Expected to fail in the starter project."""
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PROTECTED = {'docs/CURRENT_REQUIREMENTS.md': '43eb484475252cc00972663bec0eda698255af5613316dec4b1e07712b5d9cf6', 'docs/CUSTOMER_NOTE.md': '621b712ffb3fdf532bcafa92cadff3f5f6ff0822d0b4e26be089d492c74f0b1c', 'tests/test_baseline.py': 'dee5830a263cd1fd0e4761cb232b2b74b1fd240275a6f01a5350cc8b2827483e', 'sample_orders.json': 'ed81f8daa31a06c6bd0d4fd1be11da3d972d0c8f729d155b6fe5445a13867826'}

def main():
    problems = []
    for name, digest in PROTECTED.items():
        p = ROOT / name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            problems.append("Protected input changed: " + name)
    run = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                         cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(run.stdout)
    count = re.search(r"Ran (\d+) tests?", run.stdout)
    total = int(count[1]) if count else 0
    if run.returncode != 0: problems.append("The real test run failed")
    if total < 10: problems.append("At least 10 passing tests are required, including new regressions")
    if not list((ROOT / "tests").glob("test_regression*.py")):
        problems.append("Add tests/test_regression*.py without editing the baseline")
    report_path = ROOT / "outputs/release-review.md"
    if not report_path.is_file():
        problems.append("Missing outputs/release-review.md")
    else:
        report = report_path.read_text(encoding="utf-8")
        for needed in ["What changed", "Validation", "Sources", "docs/CURRENT_REQUIREMENTS.md", "docs/CUSTOMER_NOTE.md"]:
            if needed not in report: problems.append("Release review must contain: " + needed)
    log_path = ROOT / "outputs/test-results.txt"
    if not log_path.is_file():
        problems.append("Missing captured test output: outputs/test-results.txt")
    else:
        log = log_path.read_text(encoding="utf-8")
        saved_count = re.search(r"Ran (\d+) tests?", log)
        if not saved_count or int(saved_count[1]) != total or not re.search(r"^OK\s*$", log, re.M):
            problems.append("Saved test evidence must match the current passing test count")
    try:
        validation = json.loads((ROOT / "outputs/validation.json").read_text(encoding="utf-8"))
        if validation.get("test_exit_code") != 0 or validation.get("test_count") != total:
            problems.append("validation.json must report the actual passing run and test count")
        if validation.get("test_command") != "python -m unittest discover -s tests -v":
            problems.append("validation.json must identify the test command")
    except (OSError, ValueError, TypeError):
        problems.append("Missing or invalid outputs/validation.json")
    try:
        cases = json.loads((ROOT / "sample_orders.json").read_text(encoding="utf-8"))
        with (ROOT / "outputs/quote-cases.csv").open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        actual = {r["id"]: r for r in rows}
        if len(actual) != len(cases) or len(rows) != len(cases): problems.append("CSV must contain all three unique sample cases")
        for case in cases:
            for key, value in case["expected"].items():
                if actual.get(case["id"], {}).get(key) != value:
                    problems.append("Incorrect CSV result: " + case["id"] + "/" + key)
    except (OSError, ValueError, TypeError, KeyError):
        problems.append("Missing or invalid outputs/quote-cases.csv")
    try:
        handoff = json.loads((ROOT / "outputs/demo-handoff.json").read_text(encoding="utf-8"))
        if handoff.get("project") != "Atlas Checkout" or handoff.get("test_exit_code") != 0 or handoff.get("test_count") != total:
            problems.append("Phone handoff must describe this project and the current passing test count")
        if handoff.get("verification_command") != "python verify_demo.py":
            problems.append("Phone handoff must identify its verification command")
    except (OSError, ValueError, TypeError):
        problems.append("Missing or invalid outputs/demo-handoff.json")
    if problems:
        print("DEMO CHECK: NOT COMPLETE")
        for problem in problems: print("-", problem)
        return 1
    print(f"DEMO CHECK: PASS — {total} tests, protected inputs unchanged, all five deliverables verified")
    print("This checks local project evidence, not model identity or phone connectivity.")
    return 0

if __name__ == "__main__": sys.exit(main())
