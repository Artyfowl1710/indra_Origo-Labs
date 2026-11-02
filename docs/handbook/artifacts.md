# Artifacts and deliverables


The artifact panel collects recognized generated files so you can open or download them without copying filesystem paths. Preview support depends on format; some files are downloads rather than full inline renderings. Office documents require valid generated files, not merely a model saying it created one.

If a file is missing, check the tool result and the configured output folders. Artifact names must resolve uniquely within authorized output roots. Ambiguous duplicates, missing files and paths outside the permitted roots are rejected. This protects files that were never approved for sharing.

The repository publishes only a reviewed fictional example output set under `examples/recorded-run/outputs`. Your runtime `outputs/` folder is ignored by Git. Review generated reports for private paths, names, provider responses and misleading claims before deliberately adding them to a public project.

A generated report can contain an inaccurate assertion. For the recorded checkout task, compare release-review.md with test-results.txt, quote-cases.csv, the corrected source and an independent run of verify_demo.py. The report's original "expected to pass" line is preserved as generated; later recorded and independent checks are documented separately.
