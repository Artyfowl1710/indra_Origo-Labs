# Atlas Checkout — Indra recording fixture

An intentionally buggy, fictional checkout library for a real agent demonstration. This sample is not a production payment system and is not the hackathon entry itself. The entry is Indra's newly developed Meta-powered workflow around it.

Requirements: Python 3.10+; standard library only.

From this project folder:

```text
python -m unittest discover -s tests -v
python verify_demo.py
```

The initial baseline deliberately has 8 tests, with 3 failures caused by two defects. Indra should repair checkout.py, add regression tests in a new test file, and create verified outputs. The full verifier should initially fail; that is expected.

The recorded workflow must show the actual model response, requested approvals, execution and results. Do not present this prewritten sample or the pre-existing product foundation as newly implemented model output.

Read docs/CURRENT_REQUIREMENTS.md and docs/CUSTOMER_NOTE.md. Protected files must stay unchanged: docs/, tests/test_baseline.py, sample_orders.json and verify_demo.py. Allowed edits: checkout.py; new test files; outputs/.

If the execution environment maps the selected project to /workspace, run commands there. Never disable the sandbox or substitute host execution to make a blocked action pass.
