# Five-minute judge walkthrough


## Reproduce the useful result

1. Install Indra and connect Baseten with your own key. Choose `meta-models/muse-spark-open-1026` in Models. Confirm the model is available to your account.
2. Copy `examples/atlas-checkout` to a writable folder. It intentionally starts with bugs. Do not use `examples/recorded-run` as the starting state.
3. Open Chat → Projects, select that folder, and grant only that project.
4. Create a goal: "Repair checkout rounding and free-shipping boundaries against docs/CURRENT_REQUIREMENTS.md. Preserve existing tests and inputs. Add regression tests, produce a release review and machine-readable evidence, and only mark complete when python verify_demo.py exits zero."
5. Paste the prompt below. Review any requested command/edit approval. The fixture is plain Python and does not require external packages.

```text
Read the project requirements and customer note. First run the existing tests and report the baseline honestly. Fix checkout.py without changing the public quote() interface, original tests, requirements, sample_orders.json or verify_demo.py. Add regression tests for exact/just-below shipping threshold, fractional-cent half-up rounding and discount behavior. Run all tests. Create outputs/release-review.md, outputs/test-results.txt, outputs/quote-cases.csv, outputs/validation.json and outputs/demo-handoff.json from observed results. Run python verify_demo.py and report its actual exit status. Do not claim completion if the verifier fails. Ask before any network access or new dependency installation.
```

6. Open the generated artifacts, inspect test results, and run the verifier independently. The recorded completed snapshot is supplied separately for comparison.

## What the recording establishes

The published real desktop footage shows a selected Meta model, project requirements, regression test output, generated files and a goal check. The separately recorded phone task shows remote communication, a permission decision and returned files; it does not prove that its generated program executed successfully. The preferred three-minute cut uses a separate synthetic narrator and actual recorded clips throughout, including the animated product front page and a local Docker walkthrough.
