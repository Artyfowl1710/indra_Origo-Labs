# Recorded demo walkthrough


## Reproduce the useful result

1. Install Indra and connect a provider or local model server. The recording used Baseten and `meta-models/muse-spark-open-1026`. You can use another model available to you. Results depend on the model and runtime you choose.
2. Copy `examples/atlas-checkout` to a writable folder. It intentionally starts with bugs. Do not use `examples/recorded-run` as the starting state.
3. Open Chat → Projects, select that folder, and grant only that project.
4. Create a goal: "Repair checkout rounding and free-shipping boundaries against docs/CURRENT_REQUIREMENTS.md. Preserve existing tests and inputs. Add regression tests, produce a release review and machine-readable evidence, and only mark complete when python verify_demo.py exits zero."
5. Paste the prompt below. Review any requested command/edit approval. The fixture is plain Python and does not require external packages.

```text
Read the project requirements and customer note. First run the existing tests and report the baseline honestly. Fix checkout.py without changing the public quote() interface, original tests, requirements, sample_orders.json or verify_demo.py. Add regression tests for exact/just-below shipping threshold, fractional-cent half-up rounding and discount behavior. Run all tests. Create outputs/release-review.md, outputs/test-results.txt, outputs/quote-cases.csv, outputs/validation.json and outputs/demo-handoff.json from observed results. Run python verify_demo.py and report its actual exit status. Do not claim completion if the verifier fails. Ask before any network access or new dependency installation.
```

6. Open the generated artifacts, inspect test results, and run the verifier independently. The recorded completed snapshot is supplied separately for comparison.

## What the recording establishes

The desktop footage shows the selected model, project requirements, regression test output, generated files and a goal check. A separately recorded phone task shows remote communication, a permission decision and returned files. That task encountered a dependency download failure, so execution of its generated program remains unverified. The three-minute recording combines actual clips with synthetic narration and includes a Docker walkthrough.
