# Contributing to Indra

Bug reports, installation testing, documentation fixes and code contributions are welcome. Start with the [development guide](docs/handbook/development.md) and [architecture](docs/handbook/architecture.md). The native desktop entry point is `origo-desktop/`, and the root `app/` package contains the earlier standalone API.

## Report a problem

Search [existing issues](https://github.com/Artyfowl1710/indra_Origo-Labs/issues) first. A useful report includes the release or commit, operating system, steps to reproduce, expected result and observed result. For model problems, include the provider or local server, model name and relevant hardware. A small fictional project is easier to investigate than a full private workspace.

Remove credentials, account identifiers and personal content from logs and screenshots. Report vulnerabilities through [SECURITY.md](SECURITY.md).

## Make a change

Keep each pull request focused on one problem. For larger changes, describe the use case and intended approach in an issue so others can comment before implementation.

Use a fresh test profile. Preserve loopback defaults, project folder scopes, approval checks and Docker isolation. Treat documents and model output as untrusted input. Add regression coverage for changes to permissions, paths, output limits, concurrency or other API contracts. Optional integrations should remain optional and report unavailable services clearly.

Dependency changes need matching lockfile updates and runtime validation. Model compatibility reports should identify the path actually tested. Check appearance changes in light, teal and ember themes, including keyboard access and readable contrast.

Keep the product name Indra, by Origo Labs. Preserve upstream notices and compatibility identifiers, and explain which work is inherited. The [attribution record](NOTICE.md) and [development history](HACKATHON.md) describe the existing foundation.

## Check the change

From the repository root, using the environment created in the development guide, run the product checks below.

```powershell
.\.indra-python\Scripts\python.exe -m compileall -q app scripts tests
.\.indra-python\Scripts\python.exe -m unittest discover -s tests -v
.\.indra-python\Scripts\python.exe scripts/validate_extensions.py
node --check app/static/app.js
node --test origo-desktop/product-paths.test.cjs
```

Run the relevant imported-framework or workbench tests when changing those areas. Documentation and release changes also have checks described in the [testing guide](docs/handbook/testing.md). The starter checkout example has intentional failing tests. Use `examples/recorded-run/` to verify the completed demo.

In the pull request, explain the problem, what changed, the checks you ran and their results. Describe any AI assistance and how you verified the submitted changes. Keep `.env` files, runtime profiles, signing keys, messaging sessions, model weights and personal documents out of the patch.
