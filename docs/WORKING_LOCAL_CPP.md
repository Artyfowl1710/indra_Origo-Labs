# Working local llama.cpp solution · 2026-10-30

Local inference startup is working. The blocked unsigned reference binaries were not altered and Windows security policy was not changed. The official Ollama runtime was updated from 0.15.2 to 0.40.13 using its publisher-signed installer. The download matched the official release SHA-256 and had a valid Ollama Inc. Authenticode signature.

The updated installation supplies a signed `lib/ollama/llama-server.exe`. Origo launches that server directly against the existing reference GGUF files. It uses the vendor CUDA library via its full `GGML_BACKEND_PATH`, loopback binding, small batches, and no empty warm-up. This is direct llama.cpp inference; it does not require the blocked reference llama-swap executable.

## Verified results

| Check | Result |
| --- | --- |
| Reference Qwen3.5 GGUF, direct GPU chat | PASS, HTTP 200, exact expected reply |
| Reference Gemma 2 GGUF, direct GPU chat | PASS, HTTP 200, exact expected reply |
| Reference Qwen2-VL GGUF + reference projector | PASS, read INDRA42 from a synthetic image |
| Imported Indra agent, local Qwen chat | PASS |
| Imported Indra agent, local Qwen file tool | PASS, actual tool call returned fixture verification code |
| Full local profile with default tools | PASS, 14,171 input tokens, completed reply |
| Local profile provider resolution | custom provider at the active loopback /v1 endpoint |

Initial small direct requests took 64.03s for Qwen, 13.55s for Gemma, and 69.72s for the OCR image. These include cold-request work and are not steady-state benchmarks. A later cached Qwen tool follow-up logged 271 prompt tokens/sec and 37 generated tokens/sec. Do not generalize those rates to every task.

The initial 4K server was below the agent's 8K minimum. The 8K profile then failed on the desktop's larger actual tool prompt. The final Qwen server and profile both use a real 16,384-token context, verified by the full-profile test. Gemma and vision launch modes use 8,192; the full agent was tested with Qwen only.

Machine-readable results: data/test-results/direct-llamacpp.json, direct-llamacpp-vision.json, reference-local-harness.json, local-full-profile.json. Active owned PID, endpoint, model path and context are in data/cpp-runtime.json.

## Launch

Use the Windows Start menu shortcut **Indra Origo Local**, or double-click `start_origo.bat` in Origo. Both use `start_origo_cpp.ps1 -Model qwen` and open the customized Indra UI in its desktop shell.

Advanced source launch modes:

```powershell
.\start_origo_cpp.ps1 -Model qwen
.\start_origo_cpp.ps1 -Model gemma
.\start_origo_cpp.ps1 -Model vision
```

Switching models stops only the process recorded as owned by Origo, after verifying its executable path and alias. It does not terminate arbitrary processes on shared ports. The runtime reuses an owned healthy server with the requested model/context; the selected endpoint is written into Origo's separate local profile. Explicit `-Port` is supported when a stable endpoint is required.

Weights are still read from the user's SIH-26-main reference folder. That folder was not edited. The launcher therefore depends on those files and the installed vendor runtime remaining in place; distribution to another PC still needs a model-directory selector and proper bundled installer packaging. No cloud inference fallback is configured for this profile. This verifies local inference, not total network isolation of every optional product feature.

The broader imported API/build test failures documented in DOTS_FEATURE_VERIFICATION.md remain a separate product-release gate. This local startup fix does not imply those tests or every desktop workflow are green.
