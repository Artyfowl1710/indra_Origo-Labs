---
name: Local Model Benchmarking
description: Design repeatable local inference and agent-harness comparisons with clear limits.
---
# Local Model Benchmarking

1. Record hardware, OS, driver/runtime, model ID and hash, quantization, server version, chat template, context size, KV-cache settings and GPU offload.
2. Separate model-load time, time to first token, prompt processing, decode tokens/second, end-to-end task latency, peak VRAM/RAM and failures.
3. Use the same prompts, tool schemas, concurrency, context, sampling parameters and timeouts across candidates.
4. Warm up separately. Repeat trials and report median, spread and failure rate; retain raw traces.
5. Use held-out tasks for conclusions. Routing smoke tests and synthetic tool-call checks are not task-success benchmarks.
6. Separate model changes from harness changes; use ablations and compare against an unchanged baseline.
7. Stop runs that exceed budgets; do not infer speed from a single successful request or from the UI's perceived responsiveness.
8. State uncertainty and hardware-specific constraints, especially VRAM pressure and concurrent decode contention.
