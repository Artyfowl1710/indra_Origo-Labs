# Reference llama.cpp and local model audit · 2026-10-30

Status: static/model/configuration inspection completed; live llama.cpp inference BLOCKED by Windows application-control policy. The reference folder was read only. No models were downloaded, moved, deleted, or duplicated into Origo.

## Model inventory

| File | Size (decimal GB) | GGUF architecture | Declared context |
| --- | ---: | --- | ---: |
| gemma-2-2b-it-Q4_K_M.gguf | 1.709 | gemma2 | 8,192 |
| Qwen2-VL-OCR-2B-Instruct.Q4_K_M.gguf | 0.986 | qwen2vl | 32,768 |
| mmproj-Qwen2-VL-2B-Instruct-f16.gguf | 1.332 | clip projector | Not a chat model |
| Qwen3.5-4B-Q4_K_M.gguf | 3.013 | qwen35 | 262,144 |
| Qwen_Qwen3.5-4B-Q4_K_M.gguf | 3.013 | qwen35 | 262,144 |

All five files have readable GGUF v3 headers and metadata. Full-file SHA-256 hashes were calculated. The two Qwen3.5 files have the same SHA-256, 13c16f426047e2de38cd075bdade4a7bcbc8c774384876f677740cda65f8a983, and are duplicate weights. Total model storage is 10,052,341,408 bytes; unique file content is 7,039,313,600 bytes. No duplicate was removed.

The model and projector metadata both identify Qwen2 VL 2B Instruct. This is a metadata compatibility indication, not a successful vision/OCR test. The OCR label in the filename alone does not independently establish which fine-tuning weights were merged.

These hashes establish file identities, not publisher authenticity. download_models.py prints AUDIT PASS after calculating a hash without comparing against a pinned expected hash. Its comment mentions expected_sha256, but the model entries do not supply expected digests. Publisher provenance remains unverified.

Full metadata and hashes: data/test-results/llama-model-inventory.json.

## Runtime and binary inspection

The reference backend/bin contains llama-server.exe, llama-server-impl.dll, llama.dll, ggml CUDA/CPU/Vulkan libraries, llama-swap.exe, and other utilities. Import tables identify the binaries as x86-64. llama-server.exe loads llama-server-impl.dll, which imports llama.dll and ggml libraries. ggml-cuda.dll imports cublas64_13.dll; that library imports cublasLt64_13.dll.

cudart64_12.dll and cudart64_13.dll have identical hashes. The cublas64 pair and cublasLt64 pair are also identical. The _12 filenames therefore do not establish that a distinct CUDA 12 runtime is present. This build's observed import names use the _13 files. No DLL was renamed or replaced.

The inspected GPU is an NVIDIA GeForce RTX 3050 6GB Laptop GPU, with 6,144 MiB total and 4,638 MiB free at inspection time. This is a snapshot, not proof that a configured context fits or inference meets latency targets.

Full dependency/hash inventory: data/test-results/llama-binary-inventory.json.

## Confirmed Windows execution block

Version probes failed before successful runtime startup. llama-server exited with code -1058471934; llama-swap.exe failed to launch with an Application Control policy error. Both executable signatures report NotSigned.

Windows Code Integrity events 3077 and 3033 explicitly identify llama.dll and llama-swap.exe as violating enterprise signing requirements/policy ID {0283ac0f-fff1-49ae-ada1-8a933130cad6}. This is a confirmed application-control block, not a diagnosed model-file problem. Successful elevation did not remove the policy restriction. No antivirus setting, application-control rule, or protection was changed. The appropriate resolution is an administrator-approved runtime/signing policy decision; moving/renaming binaries is not a verification step.

Live generation, streaming, tool calling, OCR, image input, model swapping and memory benchmarks remain unverified for this llama.cpp stack.

## Configuration findings

- Reference llama-swap.yaml has three routes: gemma-2-2b-it, qwen2-vl-ocr-2b-instruct, qwen3.5-4b. The workbench separately translates indra-auto and other product aliases. Connecting directly to llama-swap and sending indra-auto is not equivalent to connecting through the workbench.
- Gemma is launched with --ctx-size 32768 and the workbench advertises 32768, while gemma2.context_length in its GGUF is 8192. Treat that expansion as unverified; use a context at or below the declared length for the initial baseline.
- Qwen3.5 is configured for 32768, GPU layers 99, quantized KV cache and one parallel slot. Its much larger declared context does not establish that it fits this 6GB GPU. Benchmark smaller contexts before increasing it.
- Qwen2-VL is configured for 8192 with the matching-named projector. The explicit --chat-template chatml override needs an actual image/OCR check against the model's embedded template before accepting vision behavior.
- scan_models chooses the first projector file for any detected VLM; that selection becomes ambiguous when additional vision models/projectors are added. Its duplicate-alias suppression also hides the second identical Qwen file without reporting a duplicate.
- The 4k preset maps to 4096. The eco preset maps to 8192 despite a label mentioning 4-6GB hardware. Presets apply the same requested context across models rather than clamping to each model's declared metadata.
- The generated config uses developer absolute model/binary paths. A portable Origo setup needs explicit local model-directory selection and regenerated paths; it should not hardcode the reference folder into a distributed installer.
- Neither http://127.0.0.1:8100/v1/models nor http://127.0.0.1:8000/docs was reachable during this inspection. No active llama process was observed; Ollama was present as a separate process.
- start-backend.ps1 treats an open TCP port as an existing service without verifying its identity. It also writes reference configuration/credentials when run. It was inspected but not run.

## Remaining acceptance work

After an approved runtime can execute: verify version and supported flags; start only Origo-owned loopback services with logs under Origo; test model discovery and alias routing; test chat/streaming/cancellation and bounded tool calls; test synthetic image/OCR input with its projector; measure load time, tokens/sec and peak GPU/RAM at several context sizes; verify unload/swap behavior and shutdown ownership. Local acceptance has not passed yet. The prior Dots/API failures remain a separate unresolved gate.

## Follow-up resolution
See [Working local llama.cpp solution](WORKING_LOCAL_CPP.md). A signed vendor runtime now runs all three reference models directly, and the local Qwen agent and full 16K profile tests pass. The original unsigned reference binaries remain unchanged.
