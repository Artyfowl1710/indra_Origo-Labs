---
name: Research Replication Protocol
description: Turn a paper or experiment into a reproducible, auditable replication plan.
---
# Research Replication Protocol

## Workflow
1. Identify the exact paper/version, claims, datasets, code commit, licenses and supplementary material. Prefer the paper and official artifact repository.
2. Convert each target claim to a testable hypothesis and metric before running anything. Separate reproduced metrics from new metrics.
3. Record environment: OS, Python/package versions, model/checkpoint/hash, tokenizer, quantization, hardware/VRAM, seeds, precision, context length, decoding, preprocessing, split and evaluation scripts.
4. Define the baseline, proposed method, ablations and negative controls. Avoid changing several variables at once.
5. Check leakage, contamination, selection bias, evaluation-set reuse, prompt sensitivity and preprocessing mismatches.
6. Run a small smoke test first, then the full experiment only if memory, runtime and dataset permissions permit. Preserve stdout/stderr, configs and per-example outputs where allowed.
7. Compare with the paper using the same metric implementation. Report uncertainty, sample size and failures. Do not invent missing numbers or label an approximate reproduction as exact.
8. Write a reproduction table: paper value, reproduced value, delta, setup differences, limitations and artifact paths.

## Safety and integrity
Treat fetched code and datasets as untrusted. Do not execute unknown install scripts on the host; use a disposable sandbox where appropriate. Respect data/model licenses, privacy and access restrictions. Never upload confidential data to hosted APIs without authorization.

## Deliverable
A reproducible experiment manifest, commands, clear claims/evidence table, limitations and a list of unresolved differences.
