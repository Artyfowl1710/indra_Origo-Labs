# Air-Gapped AI Workbench — Extended Setup, Runtime & Integration Guide

> **Companion document to `SETUP.md`**
>
> This document extends the basic installation guide with the runtime-specific setup required to actually deploy and operate the Workbench with local LLMs, GGUF models, VLMs, multimodal models, RAG, Artifactory, vLLM, ONNX Runtime, ComfyUI and external OpenAI-compatible clients such as Hermes.

---

# 0. What This Document Is For

The basic `SETUP.md` explains the general project installation.

This document explains the **real deployment path**:

```text
                         ┌──────────────────────┐
                         │      Hermes / UI     │
                         │ OpenAI-compatible    │
                         │ client               │
                         └──────────┬───────────┘
                                    │
                                    │ HTTP
                                    │ Bearer API key
                                    ▼
                    ┌──────────────────────────────┐
                    │      Workbench Gateway       │
                    │          :8000               │
                    │                              │
                    │  Authentication / RBAC       │
                    │  Model registry              │
                    │  Lifecycle manager           │
                    │  VRAM management             │
                    │  RAG                         │
                    │  Backend routing             │
                    └───────┬───────┬───────┬──────┘
                            │       │       │
             ┌──────────────┘       │       └──────────────┐
             ▼                      ▼                      ▼
       llama-swap                vLLM                  ComfyUI
          :8100                  :8200+                  :8400+
             │
             ▼
       llama-server
             │
             ▼
        GGUF models


                    ┌──────────────────────┐
                    │       Qdrant         │
                    │        :6333         │
                    │                      │
                    │ RAG vector database  │
                    └──────────────────────┘
```

The key principle is:

> **Workbench is the gateway/orchestrator. The actual model runtime is a separate process/backend.**

For example:

```text
Workbench
   ↓
llama-swap
   ↓
llama-server
   ↓
Qwen / Llama / Gemma / etc.
```

---

# 1. Runtime Matrix

The project supports different classes of workloads through different backends.

| Workload                          | Recommended backend                                                 |
| --------------------------------- | ------------------------------------------------------------------- |
| GGUF LLM                          | llama-swap + llama.cpp                                              |
| Small local LLM                   | llama-swap + llama.cpp                                              |
| High-throughput LLM               | vLLM                                                                |
| LoRA serving                      | vLLM                                                                |
| CPU/edge inference                | ONNX Runtime                                                        |
| Image generation                  | ComfyUI                                                             |
| Video generation                  | ComfyUI                                                             |
| Audio generation                  | ComfyUI                                                             |
| Multimodal/VLM                    | llama.cpp multimodal / suitable backend                             |
| Embeddings                        | Workbench embedding backend / supported runtime                     |
| RAG                               | Qdrant + embedding model                                            |
| External OpenAI-compatible client | Workbench `/v1/*` API                                               |
| Ollama models                     | Optional external runtime; not currently a native Workbench backend |

---

# 2. Important: Native Backend vs External Runtime

Do not confuse:

```text
Workbench supports a runtime
```

with:

```text
Workbench can talk to any OpenAI-compatible server.
```

The current Workbench codebase has backend implementations for:

* llama-swap
* vLLM
* ONNX Runtime
* ComfyUI

The repository README explicitly describes these four backend paths.

**Ollama is not currently implemented as a native Workbench backend.**

Therefore, do not register:

```text
backend = ollama
```

unless the code has first been extended with an Ollama backend.

Ollama can still be installed and used independently because Ollama exposes OpenAI-compatible APIs.

---

# 3. External Software You May Need

## 3.1 Git

Install Git:

[Git for Windows](https://git-scm.com/download/win?utm_source=chatgpt.com)

Linux:

```bash
sudo apt update
sudo apt install git
```

Verify:

```bash
git --version
```

---

# 4. Python

Recommended:

```text
Python 3.10+
```

Verify:

```bash
python --version
```

Windows:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install the project:

```bash
pip install -e .
```

---

# 5. NVIDIA GPU Setup

For NVIDIA systems, install the appropriate NVIDIA driver.

Verify:

```bash
nvidia-smi
```

Example:

```text
NVIDIA GeForce RTX 3050 Laptop GPU
6144 MiB
```

The CUDA version reported by:

```bash
nvidia-smi
```

is the driver-supported CUDA compatibility level.

It does **not** necessarily mean that every runtime must be installed using exactly that CUDA toolkit version.

---

# 6. llama.cpp — IMPORTANT

For GGUF inference, llama.cpp is one of the most important external components.

Official releases:

[llama.cpp Releases](https://github.com/ggml-org/llama.cpp/releases?utm_source=chatgpt.com)

The release page provides prebuilt binaries for multiple operating systems and accelerators, including Windows x64 CUDA builds.

---

# 7. Windows llama.cpp Installation

For an NVIDIA Windows machine:

1. Open the llama.cpp releases page.
2. Download the appropriate Windows CUDA package.
3. Choose CUDA 12 or CUDA 13 according to the runtime/driver combination.
4. Extract the package.
5. Place the required executables and DLLs into the Workbench `bin` directory.

At minimum, the GGUF serving path requires:

```text
llama-server.exe
```

and the associated GGML/CUDA DLLs.

For CUDA 13 builds, the runtime package may additionally contain libraries such as:

```text
cublas64_13.dll
cublasLt64_13.dll
cudart64_13.dll
```

Keep the required DLLs discoverable through `PATH` or beside the executable.

Example:

```powershell
$env:Path = "$PWD\bin;$env:Path"
```

Verify:

```powershell
Get-Command llama-server
```

Then:

```powershell
.\bin\llama-server.exe --version
```

---

# 8. Verify llama.cpp BEFORE Touching Workbench

This is extremely important.

Do not debug:

```text
Hermes
→ Workbench
→ llama-swap
→ llama-server
→ GPU
```

all at once.

First prove:

```text
llama-server
→ model
→ GPU
→ OpenAI API
```

works.

Example:

```powershell
.\bin\llama-server.exe `
    --model ".\models\Qwen_Qwen3.5-4B-Q4_K_M.gguf" `
    --port 5800 `
    --n-gpu-layers 99
```

Then verify:

```powershell
Invoke-RestMethod `
    -Uri "http://127.0.0.1:5800/v1/models" `
    -Method Get
```

---

# 9. Qwen3.5 Thinking Mode

Some modern reasoning models may spend the entire generation budget on reasoning.

For Qwen3.5-style models, a request can explicitly disable thinking:

```json
{
  "chat_template_kwargs": {
    "enable_thinking": false
  }
}
```

Example PowerShell:

```powershell
$body = @{
    model = "Qwen3.5-4B"
    messages = @(
        @{
            role = "user"
            content = "Say hello in one short sentence."
        }
    )
    max_tokens = 100
    chat_template_kwargs = @{
        enable_thinking = $false
    }
} | ConvertTo-Json -Depth 10 -Compress
```

Then:

```powershell
$r = Invoke-RestMethod `
    -Uri "http://127.0.0.1:5800/v1/chat/completions" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

$r.choices[0].message.content
```

Expected:

```text
Hello!
```

This test confirms that:

```text
Model
✓ loaded
✓ GPU works
✓ llama-server works
✓ OpenAI-compatible endpoint works
✓ chat template works
```

before introducing Workbench.

---

# 10. llama-swap

Workbench uses llama-swap to manage GGUF models.

The architecture is:

```text
Workbench
    ↓
llama-swap
    ↓
llama-server
    ↓
GGUF
```

Official llama-swap repository:

[llama-swap on GitHub](https://github.com/mostlygeek/llama-swap?utm_source=chatgpt.com)

Check the binary:

```powershell
.\bin\llama-swap.exe --version
```

---

# 11. llama-swap Version Compatibility

This is an important deployment warning.

The Workbench backend was written against an older llama-swap command/configuration interface.

Newer llama-swap releases may use:

```text
--listen
```

instead of the older:

```text
--port
```

and may expect model configurations containing:

```yaml
cmd:
```

with:

```text
${PORT}
```

rather than only:

```yaml
model:
args:
```

Therefore:

> **Do not blindly update llama-swap to the newest release and assume the Workbench integration will remain compatible.**

If a deployment uses a newer llama-swap release, validate:

```powershell
.\bin\llama-swap.exe --help
```

and:

```powershell
.\bin\llama-swap.exe --validate
```

before starting Workbench.

---

# 12. Direct llama-swap Test

For a modern llama-swap configuration, an example configuration is:

```yaml
models:
  qwen3.5-4b:
    cmd: llama-server --port ${PORT} --model "C:\path\to\models\Qwen_Qwen3.5-4B-Q4_K_M.gguf"
```

Validate:

```powershell
.\bin\llama-swap.exe `
    --config .\config\llama-swap.yaml `
    --validate
```

Expected:

```text
config is valid
```

Start:

```powershell
.\bin\llama-swap.exe `
    --config .\config\llama-swap.yaml `
    --listen 127.0.0.1:8100
```

Then:

```powershell
Invoke-RestMethod `
    -Uri "http://127.0.0.1:8100/v1/models" `
    -Method Get
```

The model may initially show:

```text
status: unloaded
```

That is normal.

Send a request:

```text
POST /v1/chat/completions
```

The first request should cause llama-swap to start the corresponding llama-server process.

---

# 13. Model Files

For GGUF models:

```text
models/
    Qwen_Qwen3.5-4B-Q4_K_M.gguf
```

Example registration:

```powershell
workbench models add qwen3.5-4b `
    --source ".\models\Qwen_Qwen3.5-4B-Q4_K_M.gguf" `
    --backend llamaswap `
    --type text `
    --task chat `
    --vram-mb 4500
```

Then:

```powershell
workbench models list
```

Expected:

```text
qwen3.5-4b | llamaswap | text | cold | 4500 | chat
```

---

# 14. GPU VRAM Estimation

The `--vram-mb` value is a reservation/management estimate.

It is NOT necessarily equal to:

```text
GGUF file size
```

because actual runtime memory also depends on:

* KV cache
* context length
* CUDA buffers
* compute buffers
* multimodal projector
* batch size
* parallel requests
* runtime overhead

For a 6 GB GPU, do not simply register every model as:

```text
6144 MB
```

Leave headroom for the runtime and operating system.

---

# 15. Starting the Complete Workbench

The recommended bare-process path is:

```powershell
workbench up
```

The launcher starts:

```text
Qdrant
Gateway
```

The llama-swap backend is brought up when required by model loading.

Check:

```powershell
workbench status
```

Set the CLI API base explicitly if necessary:

```powershell
$env:WORKBENCH_API_BASE = "http://127.0.0.1:8000"
```

Set the API key:

```powershell
$env:WORKBENCH_API_KEY = "<USER_API_KEY>"
```

Then:

```powershell
workbench status
```

---

# 16. API Keys

The recommended architecture is:

```text
ADMIN KEY
    ↓
administrative operations

USER KEY
    ↓
inference
```

Do NOT give the administrator key to Hermes or another end-user client.

Create a normal user key using the administrative CLI:

```powershell
workbench admin keys create --owner <name> --scope user
```

Store the resulting key securely.

Then configure clients with the USER key.

---

# 17. Workbench OpenAI-Compatible API

The primary endpoint is:

```text
/v1/chat/completions
```

For example:

```text
http://127.0.0.1:8000/v1/chat/completions
```

The API follows the OpenAI-style request format.

Example:

```json
{
  "model": "qwen3.5-4b",
  "messages": [
    {
      "role": "user",
      "content": "Hello"
    }
  ],
  "max_tokens": 100
}
```

Authentication:

```http
Authorization: Bearer <USER_API_KEY>
```

---

# 18. Test Workbench Directly

Before connecting Hermes, test the gateway itself.

PowerShell:

```powershell
$body = @{
    model = "qwen3.5-4b"
    messages = @(
        @{
            role = "user"
            content = "Say hello in one short sentence."
        }
    )
    max_tokens = 100
    chat_template_kwargs = @{
        enable_thinking = $false
    }
} | ConvertTo-Json -Depth 10 -Compress
```

Then:

```powershell
$r = Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/v1/chat/completions" `
    -Method Post `
    -ContentType "application/json" `
    -Headers @{
        Authorization = "Bearer $env:WORKBENCH_API_KEY"
    } `
    -Body $body
```

Inspect:

```powershell
$r | ConvertTo-Json -Depth 20
```

Then:

```powershell
$r.choices[0].message.content
```

Expected:

```text
Hello!
```

At this point the entire chain has been proven:

```text
PowerShell
 ↓
Workbench :8000
 ↓
Lifecycle Manager
 ↓
llama-swap :8100
 ↓
llama-server
 ↓
GGUF
 ↓
NVIDIA GPU
```

---

# 19. curl Test

Linux/macOS:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer $WORKBENCH_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.5-4b",
    "messages": [
      {
        "role": "user",
        "content": "Say hello in one short sentence."
      }
    ],
    "max_tokens": 100,
    "chat_template_kwargs": {
      "enable_thinking": false
    }
  }'
```

Windows PowerShell should preferably use:

```powershell
Invoke-RestMethod
```

or explicitly invoke:

```powershell
curl.exe
```

rather than relying on PowerShell's `curl` alias.

---

# 20. Hermes Integration

Once this works:

```text
http://127.0.0.1:8000/v1/chat/completions
```

Hermes should **not** connect directly to llama-server.

It should connect to:

```text
Workbench
```

Conceptually configure Hermes:

```text
Provider:
    OpenAI-compatible

Base URL:
    http://<WORKBENCH_HOST>:8000/v1

API Key:
    <USER_API_KEY>

Model:
    qwen3.5-4b
```

If Hermes expects the base URL without `/v1`, use the format required by its OpenAI-compatible provider configuration.

The important point is:

```text
Hermes
   ↓
OpenAI-compatible placeholder
   ↓
Workbench USER API key
   ↓
Workbench /v1/chat/completions
```

Do not expose the llama-swap or llama-server ports directly to Hermes.

---

# 21. Remote Hermes Client

If Hermes is on another machine:

```text
Hermes PC
     │
     │ HTTP/HTTPS
     ▼
Workbench Server
     │
     ├── :8000 Gateway
     ├── :6333 Qdrant
     ├── :8100 llama-swap
     └── internal model processes
```

Only the gateway should normally be exposed.

Do NOT expose:

```text
8100
6333
5800
```

to the client unless there is a specific operational reason.

Use a reverse proxy/TLS layer for production deployment.

---

# 22. HTTP vs HTTPS

Development:

```text
http://127.0.0.1:8000
```

LAN/production:

```text
https://workbench.example.internal
```

The Workbench configuration includes TLS-related server configuration, but client configuration must match the actual deployment.

For Hermes:

```text
Base URL = https://workbench.example.internal/v1
```

not:

```text
https://workbench.example.internal/v1/chat/completions
```

unless Hermes specifically asks for a full endpoint.

---

# 23. Artifactory Deployment

Artifactory is optional for a normal laptop deployment.

There are two main modes.

## Mode A — Local Models

```text
Workbench
    ↓
local models/
    ↓
GGUF
```

This is easiest for development.

Set:

```env
ARTIFACTORY_URL=
ARTIFACTORY_REPO=
ARTIFACTORY_USER=
ARTIFACTORY_TOKEN=
```

and manually place model files in the configured models directory.

---

## Mode B — Private Artifactory

Enterprise deployment:

```text
Workbench
     ↓
Private Artifactory
     ↓
Model artifact
     ↓
Local model cache
     ↓
Backend
```

Configure:

```env
ARTIFACTORY_URL=http://artifactory.internal/artifactory
ARTIFACTORY_REPO=models
ARTIFACTORY_USER=<user>
ARTIFACTORY_TOKEN=<token>
```

The current `.env.example` documents Artifactory as the model-storage path for air-gapped deployment.

---

# 24. Air-Gapped Mode

For a truly air-gapped environment:

```env
ALLOW_HF_DOWNLOAD=false
```

Do not depend on Hugging Face downloads during runtime.

Models should be:

```text
preloaded
```

or:

```text
retrieved from internal Artifactory
```

The repository is explicitly designed around this offline-first architecture.

---

# 25. Non-Air-Gapped Development Mode

For a laptop/Kaggle development environment, Hugging Face downloads can be allowed when appropriate:

```env
ALLOW_HF_DOWNLOAD=true
```

This should NOT be used casually in a true air-gapped environment.

---

# 26. RAG — No RAG

RAG is optional.

A plain inference deployment requires only:

```text
Workbench
+
model runtime
```

Example:

```text
Hermes
 ↓
Workbench
 ↓
Qwen
```

No Qdrant retrieval is required for ordinary chat.

---

# 27. RAG — With Qdrant

With RAG:

```text
                    ┌───────────────┐
                    │ User Question │
                    └───────┬───────┘
                            │
                            ▼
                    Embedding Model
                            │
                            ▼
                       Qdrant :6333
                            │
                            ▼
                    Relevant Documents
                            │
                            ▼
                         LLM
```

Qdrant is the vector database.

Configuration:

```env
QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333
```

---

# 28. RAG Embedding Model

Register an embedding-capable model and set:

```env
RAG_EMBEDDING_MODEL_ID=<registered_embedding_model>
```

The model ID must match the Workbench model registry.

Do not set:

```env
RAG_EMBEDDING_MODEL_ID=random-name
```

unless that model actually exists in the registry.

---

# 29. RAG Deployment Modes

### No RAG

```text
QDRANT not required by client
```

### Local RAG

```text
Workbench
 ↓
Qdrant localhost
 ↓
Local embedding model
```

### Enterprise RAG

```text
Workbench
 ↓
Internal Qdrant
 ↓
Internal embedding model
 ↓
Private documents
```

---

# 30. vLLM

vLLM is intended for high-throughput model serving.

Official documentation:

[vLLM OpenAI-Compatible Server Documentation](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/?utm_source=chatgpt.com)

vLLM exposes OpenAI-compatible APIs and supports OpenAI-style chat/completion serving.

Use vLLM when:

```text
GPU memory is sufficient
+
high throughput matters
+
model is supported by vLLM
```

Typical deployment:

```text
Workbench
    ↓
vLLM
    ↓
LLM
```

vLLM is generally preferable to llama.cpp for:

* large GPU servers
* throughput-heavy workloads
* concurrent requests
* LoRA serving
* enterprise GPU infrastructure

---

# 31. llama.cpp vs vLLM

Use:

```text
llama.cpp
```

when:

* model is GGUF
* local development matters
* VRAM is limited
* consumer GPU
* laptop deployment
* edge deployment
* CPU fallback is useful

Use:

```text
vLLM
```

when:

* NVIDIA GPU infrastructure is available
* model architecture is supported
* throughput matters
* multiple users are expected
* LoRA serving is required

---

# 32. ONNX Runtime

ONNX Runtime is intended for efficient cross-platform/edge inference.

Use it for models exported to ONNX.

Typical architecture:

```text
Workbench
    ↓
ONNX Runtime
    ↓
ONNX model
    ↓
CPU/GPU
```

This is particularly useful when deploying models where a full LLM runtime would be excessive.

---

# 33. ComfyUI

ComfyUI is the main workflow-oriented backend for generative media.

Official project:

[ComfyUI on GitHub](https://github.com/comfyanonymous/ComfyUI?utm_source=chatgpt.com)

The Workbench repository describes ComfyUI integration for image, video and audio generation.

Conceptually:

```text
Workbench
    ↓
ComfyUI
    ↓
Workflow
    ├── text encoder
    ├── diffusion model
    ├── VAE
    ├── audio/video nodes
    └── output
```

---

# 34. Image Generation

Image generation should use a ComfyUI workflow.

Examples include:

```text
Text → Image
Image → Image
ControlNet
Upscaling
Inpainting
```

The exact workflow depends on the installed ComfyUI nodes and models.

---

# 35. Video Generation

Video generation is also workflow-based.

The server architecture should be treated as:

```text
Workbench
 ↓
ComfyUI
 ↓
Video workflow
 ↓
Output
```

Do not assume every video model works on every GPU.

Video models can have extremely high:

* VRAM requirements
* RAM requirements
* context requirements
* disk requirements

---

# 36. Audio Generation

Audio generation can similarly be routed through ComfyUI where an appropriate workflow/runtime is available.

The Workbench repository explicitly lists audio generation among its ComfyUI-oriented capabilities.

---

# 37. VLM / Vision Models

For vision-language models:

```text
Image
 +
Text
 ↓
VLM
 ↓
Text response
```

Examples include models in the Qwen-VL, Gemma vision, SmolVLM and related families.

The important distinction is:

```text
LLM
```

versus:

```text
VLM
```

A normal GGUF text model cannot magically understand an image.

A multimodal-capable model and its required multimodal projector/components must be available.

---

# 38. llama.cpp Multimodal Support

Modern llama.cpp supports multimodal input through its multimodal tooling.

The llama.cpp server documentation describes multimodal support through the OpenAI-compatible chat endpoint.

The multimodal documentation currently describes:

```text
image input
audio input
```

with audio support still described as experimental.

For models requiring a separate multimodal projector, use:

```text
--mmproj
```

Example concept:

```bash
llama-server \
    -m model.gguf \
    --mmproj mmproj-model.gguf
```

The exact command depends on the model.

---

# 39. VLM Model Layout

A VLM deployment may look like:

```text
models/
    vision-model.gguf
    mmproj-model.gguf
```

Then:

```text
llama-server
    │
    ├── language model
    │
    └── multimodal projector
```

Do not assume that every VLM requires an external `mmproj`; some model packages may bundle or otherwise handle multimodal components differently.

Always follow the model's llama.cpp compatibility instructions.

---

# 40. OCR

OCR can be implemented through several model classes.

### OCR through a VLM

```text
Image
 ↓
Vision encoder
 ↓
VLM
 ↓
Text
```

This is useful for:

* documents
* screenshots
* tables
* forms
* handwritten text
* visual question answering

### Dedicated OCR model

Alternatively:

```text
Image
 ↓
OCR model
 ↓
Text
 ↓
RAG / LLM
```

This is often preferable for high-volume document OCR.

---

# 41. Document Intelligence

A full document pipeline can be:

```text
PDF/Image
    ↓
OCR / VLM
    ↓
Structured text
    ↓
Chunking
    ↓
Embedding model
    ↓
Qdrant
    ↓
Retriever
    ↓
LLM
```

This is the recommended conceptual architecture for enterprise document RAG.

---

# 42. Multimodal OpenAI-Compatible Requests

A multimodal-compatible runtime may accept messages where the content contains multiple parts, for example:

```json
{
  "model": "vision-model",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "What is shown in this image?"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/jpeg;base64,..."
          }
        }
      ]
    }
  ]
}
```

However:

> **The exact multimodal request format must match the backend and model.**

Do not assume that a text-only model registered as `type=vlm` suddenly gains vision support.

---

# 43. Audio Input

For audio-capable models/runtime combinations:

```text
Audio
 ↓
Audio-capable model
 ↓
Text / analysis
```

llama.cpp currently documents audio input support in its multimodal stack, but labels audio as experimental.

For production audio workloads, validate the exact model/runtime combination independently before putting it behind the gateway.

---

# 44. Ollama

Ollama is an excellent local model runtime and exposes an OpenAI-compatible API.

Official OpenAI compatibility documentation:

[Ollama OpenAI Compatibility](https://docs.ollama.com/api/openai-compatibility?utm_source=chatgpt.com)

Example architecture:

```text
Hermes
   ↓
Ollama :11434
```

Ollama's OpenAI-compatible endpoint can be used with clients expecting OpenAI-style APIs.

However, in the current Workbench repository:

```text
Ollama ≠ native Workbench backend
```

Therefore the correct deployment documentation is:

```text
Option A:
Hermes → Workbench → llama.cpp/vLLM/etc.

Option B:
Hermes → Ollama directly

Future:
Hermes → Workbench → Ollama
```

The third option requires implementing an Ollama backend/adapter in Workbench.

---

# 45. Installing Ollama

Official installation:

[Ollama Download](https://ollama.com/download?utm_source=chatgpt.com)

Linux installation is also documented by Ollama:

[Ollama Linux Installation](https://docs.ollama.com/linux?utm_source=chatgpt.com)

Verify:

```bash
ollama --version
```

Start:

```bash
ollama serve
```

Then:

```text
http://127.0.0.1:11434
```

The OpenAI-compatible API uses:

```text
http://127.0.0.1:11434/v1/
```

---

# 46. Do Not Run Multiple Servers on the Same Port

This caused confusion during development.

These are different services:

```text
Workbench       :8000
llama-swap      :8100
Qdrant          :6333
llama-server    dynamic
Ollama          :11434
```

Only one process can own a TCP port.

For example:

```text
uvicorn :8000
```

cannot be started twice.

Likewise:

```text
llama-swap :8100
```

cannot be started twice.

A user terminal with a USER API key is **not another server**.

It is simply a client of the same gateway.

---

# 47. Recommended Debugging Order

When something fails, NEVER debug the entire stack simultaneously.

Use this order:

## Level 1

```text
GPU
```

Check:

```bash
nvidia-smi
```

## Level 2

```text
Runtime
```

Example:

```bash
llama-server --version
```

## Level 3

```text
Model
```

Directly run the model with llama-server.

## Level 4

```text
Runtime API
```

Test:

```text
/v1/models
/v1/chat/completions
```

## Level 5

```text
llama-swap
```

Test:

```text
:8100/v1/models
```

and:

```text
:8100/v1/chat/completions
```

## Level 6

```text
Workbench
```

Test:

```text
:8000/v1/chat/completions
```

## Level 7

```text
Hermes
```

Only after the previous six work.

---

# 48. Minimal Smoke Test

Every new deployment should pass these tests.

### Test 1 — GPU

```bash
nvidia-smi
```

### Test 2 — Python

```bash
python --version
```

### Test 3 — llama-server

```bash
llama-server --version
```

### Test 4 — model

Start a known-good GGUF.

### Test 5 — llama-server API

```text
GET /v1/models
```

### Test 6 — direct completion

```text
POST /v1/chat/completions
```

### Test 7 — llama-swap

```text
GET http://127.0.0.1:8100/v1/models
```

### Test 8 — Workbench

```powershell
workbench status
```

### Test 9 — Workbench inference

```text
POST http://127.0.0.1:8000/v1/chat/completions
```

### Test 10 — Hermes

Configure:

```text
Base URL → Workbench
API key → USER key
Model → registered model ID
```

---

# 49. Deployment Profiles

## Profile A — Tiny Developer Laptop

```text
Python
Workbench
Qdrant
llama.cpp
GGUF
```

No:

```text
Artifactory
vLLM
ComfyUI
Docker
```

required.

---

## Profile B — GPU Developer

```text
Python
Workbench
Qdrant
llama.cpp
vLLM
ComfyUI
NVIDIA GPU
```

---

## Profile C — Enterprise Air-Gapped

```text
Workbench
      │
      ├── Artifactory
      ├── Qdrant
      ├── vLLM
      ├── llama.cpp
      ├── ComfyUI
      └── ONNX Runtime
```

No public model downloads.

---

## Profile D — Hermes Client

The Hermes machine does NOT need:

```text
Qdrant
llama.cpp
vLLM
ComfyUI
```

if another machine is hosting the Workbench.

It only needs network access to:

```text
https://<workbench-host>/v1
```

and:

```text
USER API KEY
```

---

# 50. Recommended Production Network Layout

```text
                         INTERNAL NETWORK

              ┌──────────────────────────┐
              │          Hermes          │
              │       Client / UI        │
              └────────────┬─────────────┘
                           │
                           │ HTTPS :443
                           ▼
              ┌──────────────────────────┐
              │ Reverse Proxy / Nginx    │
              └────────────┬─────────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │   Workbench Gateway      │
              │          :8000           │
              └────────────┬─────────────┘
                           │
          ┌────────────────┼─────────────────┐
          │                │                 │
          ▼                ▼                 ▼
     llama-swap          vLLM             ComfyUI
       :8100             :8200+            :8400+
          │
          ▼
    llama-server
          │
          ▼
       Models

          ┌────────────────────────────┐
          │          Qdrant            │
          │           :6333            │
          └────────────────────────────┘

          ┌────────────────────────────┐
          │       Artifactory          │
          │       Internal only        │
          └────────────────────────────┘
```

---

# 51. Security Rules

Never give Hermes:

```text
ADMIN API KEY
```

Give it:

```text
USER API KEY
```

Never expose unnecessarily:

```text
Qdrant :6333
llama-swap :8100
llama-server dynamic ports
ComfyUI :8400+
```

Prefer exposing:

```text
443 → reverse proxy → Workbench :8000
```

---

# 52. Common Failure Modes

## `llama-swap binary not found`

Check:

```powershell
Test-Path .\bin\llama-swap
Test-Path .\bin\llama-swap.exe
```

If the Workbench expects a path without `.exe`, Windows may require an appropriate executable alias/hardlink or a compatible binary layout.

---

## `flag provided but not defined: -port`

Your llama-swap binary and Workbench integration are using different CLI versions.

Check:

```powershell
.\bin\llama-swap.exe --help
```

Modern versions may use:

```text
--listen
```

instead.

---

## `no router for requested model`

Check:

```text
/v1/models
```

on llama-swap.

If the model is absent, llama-swap did not load/register the route.

---

## `exec: "llama-server": executable file not found`

Check:

```powershell
Get-Command llama-server
```

and:

```powershell
$env:Path
```

The llama-swap process must inherit a PATH containing `llama-server.exe`.

---

## `content` is empty but `reasoning_content` is populated

The model is probably spending the token budget in reasoning mode.

Try:

```json
"chat_template_kwargs": {
    "enable_thinking": false
}
```

or use the appropriate reasoning controls supported by the runtime/model.

---

## HTTP 500 from Workbench

Do not immediately blame the API.

Check:

```text
Workbench
 ↓
llama-swap
 ↓
llama-server
```

individually.

---

## HTTP 404 from llama-swap

Usually:

```text
model route does not exist
```

Check:

```text
GET /v1/models
```

and verify the requested model ID exactly matches the registered model.

---

## HTTP 401 / 403

Check:

```text
API key
scope
Authorization header
```

Use a USER key for inference.

---

## HTTP 10048 / address already in use

Another process owns the port.

Windows:

```powershell
netstat -ano | findstr ":8000"
```

or:

```powershell
netstat -ano | findstr ":8100"
```

Then inspect the PID:

```powershell
Get-Process -Id <PID>
```

---

# 53. Handover Procedure

A teammate receiving this project should be able to follow this exact sequence.

### Step 1

Clone repository.

### Step 2

Install Python.

### Step 3

Create virtual environment.

### Step 4

Install:

```bash
pip install -e .
```

### Step 5

Install NVIDIA driver if using NVIDIA.

### Step 6

Verify:

```bash
nvidia-smi
```

### Step 7

Install/download llama.cpp.

[llama.cpp Releases](https://github.com/ggml-org/llama.cpp/releases?utm_source=chatgpt.com)

### Step 8

Put:

```text
llama-server
llama-swap
required DLLs
```

in the appropriate `bin/` layout.

### Step 9

Put a known-good GGUF into:

```text
models/
```

### Step 10

Test llama-server directly.

### Step 11

Test llama-swap directly.

### Step 12

Create Workbench admin key.

### Step 13

Create Workbench user key.

### Step 14

Register model.

### Step 15

Start:

```bash
workbench up
```

### Step 16

Run:

```bash
workbench status
```

### Step 17

Call:

```text
/v1/chat/completions
```

using the USER key.

### Step 18

Connect Hermes.

### Step 19

Use:

```text
Workbench URL
+
USER API key
+
model ID
```

### Step 20

Only then add:

```text
RAG
Artifactory
VLM
OCR
ComfyUI
vLLM
additional models
```

---

# 54. Final Architecture Checklist

A deployment is considered healthy when:

```text
[ ] Python installed
[ ] Virtual environment works
[ ] Dependencies installed
[ ] NVIDIA driver works (if GPU)
[ ] nvidia-smi works
[ ] llama-server works independently
[ ] GGUF loads independently
[ ] llama-swap works independently
[ ] llama-swap can spawn llama-server
[ ] Qdrant works
[ ] Workbench starts
[ ] Workbench status is healthy
[ ] Model is registered
[ ] User API key works
[ ] /v1/models works
[ ] /v1/chat/completions works
[ ] curl/Invoke-RestMethod works
[ ] Hermes can reach Workbench
[ ] Hermes uses USER key
[ ] Hermes receives model responses
```

Only after this checklist passes should the deployment be considered handed over successfully.

---

# 55. The Golden Rule

When onboarding another machine:

> **First make the model work. Then make the runtime work. Then make Workbench work. Then make Hermes work.**

Never start by debugging Hermes.

The correct progression is:

```text
GPU
 ↓
llama-server
 ↓
GGUF
 ↓
llama-swap
 ↓
Workbench
 ↓
OpenAI-compatible API
 ↓
Hermes
```

For multimodal:

```text
GPU
 ↓
llama-server + multimodal model/projector
 ↓
multimodal API
 ↓
llama-swap
 ↓
Workbench
 ↓
Hermes / VLM client
```

For RAG:

```text
Document
 ↓
OCR / parser
 ↓
Embedding model
 ↓
Qdrant
 ↓
Retriever
 ↓
Workbench
 ↓
LLM
```

For enterprise model distribution:

```text
Artifactory
 ↓
Workbench
 ↓
local model cache
 ↓
runtime
 ↓
GPU
```

This separation makes failures dramatically easier to diagnose.

---

# 56. External Reference Links

### Core

* Repository: [Summertime-server](https://github.com/Artyfowl1710/Summertime-server?utm_source=chatgpt.com)
* llama.cpp releases: [llama.cpp Releases](https://github.com/ggml-org/llama.cpp/releases?utm_source=chatgpt.com)
* llama.cpp server documentation: [llama.cpp Server Documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md?utm_source=chatgpt.com)
* llama.cpp multimodal documentation: [llama.cpp Multimodal Documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md?utm_source=chatgpt.com)

### Runtime

* llama-swap: [llama-swap GitHub](https://github.com/mostlygeek/llama-swap?utm_source=chatgpt.com)
* vLLM: [vLLM Documentation](https://docs.vllm.ai/?utm_source=chatgpt.com)
* vLLM OpenAI server: [vLLM OpenAI-Compatible Server](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/?utm_source=chatgpt.com)
* Ollama: [Ollama](https://ollama.com/?utm_source=chatgpt.com)
* Ollama OpenAI compatibility: [Ollama OpenAI Compatibility](https://docs.ollama.com/api/openai-compatibility?utm_source=chatgpt.com)
* ComfyUI: [ComfyUI GitHub](https://github.com/comfyanonymous/ComfyUI?utm_source=chatgpt.com)

### Infrastructure

* Git: [Git](https://git-scm.com/?utm_source=chatgpt.com)
* Python: [Python](https://www.python.org/?utm_source=chatgpt.com)
* Qdrant: [Qdrant](https://qdrant.tech/?utm_source=chatgpt.com)

---

# 57. Handover Philosophy

This project should be handed over as a **runtime-agnostic inference gateway**, not as "a Qwen server".

The model can change:

```text
Qwen
Llama
Gemma
Mistral
etc.
```

The runtime can change:

```text
llama.cpp
vLLM
ONNX Runtime
ComfyUI
```

The workload can change:

```text
text
RAG
vision
OCR
audio
image generation
video generation
```

while the client interface remains:

```text
OpenAI-compatible API
```

That is the central contract of the system.
