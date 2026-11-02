# Testing and evidence


## Product checks

```powershell
.\.indra-python\Scripts\python.exe -m compileall -q app scripts tests
.\.indra-python\Scripts\python.exe -m unittest discover -s tests -v
.\.indra-python\Scripts\python.exe scripts/validate_extensions.py
node --check app/static/app.js
node --test origo-desktop/product-paths.test.cjs
```

The imported foundation also contains its own pytest suite and the workbench contains Vitest tests. Run the focused regressions for the changed area; the full imported suite is substantially larger and includes optional services/platform assumptions. Do not describe a focused pass as all framework tests passing.

## Example project checks

The starter `examples/atlas-checkout` intentionally has failing tests. A failure there before the agent works is the expected baseline. The separate `examples/recorded-run` contains the actual completed demo source and 12-test output. Independently run its tests and `python verify_demo.py` to verify the snapshot. A demo task's tests measure that task, not the whole product.

## Release checks

Read `provenance/release-validation.json` for the checks actually run for this package. Public-package checks reject runtime secrets/large files and validate handbook links. Fresh-profile packaged startup tests must use a separate test directory and no personal API credentials. An independent clean Windows PC installation remains a separate acceptance test.
