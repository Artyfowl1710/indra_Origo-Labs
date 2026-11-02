---
name: Safe Data Analysis
description: Analyze local CSV, JSON and logs with bounded, privacy-aware reproducible steps.
---
# Safe Data Analysis

## Workflow
1. Inspect file names, formats, sizes and headers before reading full contents. Reject or sample unexpectedly large files.
2. Identify sensitive columns, credentials, personal data and proprietary fields. Keep raw data local and avoid copying values into prompts unless necessary and authorized.
3. Record row/column counts, missingness, duplicate keys, schema inconsistencies, timestamp/time-zone assumptions and sampling strategy.
4. Use deterministic transformations and record parameters. Separate cleaning, exploratory analysis, hypothesis testing and visualization.
5. Validate calculations on a small hand-checkable example. Check units, denominators, leakage and multiple-comparison issues.
6. Do not write over source data. Write derived outputs separately and make reversible proposals for edits to project files.
7. Summarize key results with caveats, sample counts, exclusions, uncertainty and the exact code/commands used.

## Output
A compact data-quality report, methodology, verified result table, limitations and reproducibility notes. Clearly label estimates and never fabricate a chart, metric, or observation.
