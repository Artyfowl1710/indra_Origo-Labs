# Air-Gapped AI Workbench

## Complete Setup, Deployment & Handoff Guide

**Repository:** `Artyfowl1710/Summertime-server`
**Validated development environment:** Windows 11 + NVIDIA RTX 3050 6 GB + Python virtual environment + native Qdrant + native llama-swap + native llama.cpp
**Architecture:** FastAPI gateway + SQLite + Qdrant + model lifecycle manager + llama-swap/vLLM/ONNX/ComfyUI backends.

---

# 0. What this system actually is

The Air-Gapped AI Workbench is an OpenAI-compatible inference/orchestration gateway.

The important distinction is:

```text
                    ┌─────────────────────────────┐
                    │       Hermes / Client       │
                    │ OpenAI-compatible endpoint  │
                    └──────────────┬──────────────┘
                                   │
                         HTTP / Bearer API key
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │   Workbench Gateway :8000  │
                    │          FastAPI             │
                    └──────────────┬──────────────┘
                                   │
                     Model lifecycle / routing
                                   │
             ┌─────────────────────┼─────────────────────┐
             │                     │                     │
             ▼                     ▼                     ▼
       llama-swap                vLLM                 ONNX
          :8100                  :8200+               :8300+
             │
             ▼
       llama-server
             │
             ▼
        GGUF model
             │
             ▼
          NVIDIA GPU

                           AND

                    ┌─────────────────┐
                    │     Qdrant      │
                    │     :6333       │
                    └────────┬────────┘
                             │
                         RAG vectors
```

The gateway exposes OpenAI-compatible endpoints such as:

```text
POST /v1/chat/completions
POST /v1/embeddings
```

and RAG endpoints:

```text
POST /v1/rag/ingest
POST /v1/rag/query
```

The repository explicitly documents the OpenAI-compatible API and the multi-backend architecture.

---

# 1. Repository

Clone the official repository:

[Summertime-server GitHub repository](https://github.com/Artyfowl1710/Summertime-server?utm_source=chatgpt.com)

```bash
git clone https://github.com/Artyfowl1710/Summertime-server.git
cd Summertime-server
```

The repository currently contains:

```text
config/
data/
nginx/
server/
tests/
ui/
Dockerfile
docker-compose.yml
requirements.txt
pyproject.toml
SETUP.md
.env.example
```

---

# 2. Choose your deployment mode

There are three practical deployment modes.

## Mode A — Native/Bare-metal

Recommended for:

* development laptops
* Windows
* Kaggle/cloud notebook environments
* debugging
* machines where Docker is unavailable

This is the mode used during the validated Windows setup.

```text
Windows/Linux
    │
    ├── Python
    ├── FastAPI gateway
    ├── Qdrant binary
    ├── llama-swap binary
    └── llama.cpp binaries
```

## Mode B — Docker

Recommended for:

* controlled Linux deployments
* production
* environments where container isolation is desired
* the secure code-execution sandbox

The repository includes `docker-compose.yml`.

## Mode C — Enterprise/Air-gapped

The actual intended architecture is:

```text
Internal network
       │
       ├── Workbench gateway
       ├── Internal Artifactory
       ├── Qdrant
       └── local inference engines
```

No Hugging Face/OpenAI/public internet access is required during normal operation if all model artifacts are already available internally.

---

# 3. Required software

## 3.1 Git

### Windows

[Git for Windows — official download](https://gitforwindows.org/?utm_source=chatgpt.com)

or:

```powershell
winget install --id Git.Git -e --source winget
```

The official Git installer currently provides x64 Windows builds.

---

# 4. Python

Use Python 3.10+.

For reproducibility, Python 3.11 is a good choice for this project.

[Python official downloads](https://www.python.org/downloads/?utm_source=chatgpt.com)

Verify:

```powershell
python --version
```

Expected:

```text
Python 3.11.x
```

If `python` is not found, install Python and restart the terminal.

---

# 5. NVIDIA GPU setup

A GPU is **not required for every backend**, but is strongly recommended for local LLM inference.

For NVIDIA:

```powershell
nvidia-smi
```

You should see the GPU and driver.

Example validated hardware:

```text
GPU: NVIDIA GeForce RTX 3050 Laptop GPU
VRAM: 6144 MiB
Compute Capability: 8.6
```

Install/update drivers from:

[NVIDIA Driver Downloads](https://www.nvidia.com/Download/index.aspx?utm_source=chatgpt.com)

You do **not** necessarily need to install the complete CUDA Toolkit merely to run the prebuilt llama.cpp CUDA binaries. The Windows llama.cpp release packages include CUDA runtime DLL packages.

---

# 6. Install the Python environment

From the repository root:

### Windows PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then:

```powershell
.\venv\Scripts\Activate.ps1
```

You should see:

```text
(venv) PS C:\...\Summertime-server>
```

---

# 7. Install Python dependencies

Install the project:

```powershell
pip install -e .
```

If the project is using the requirements file instead:

```powershell
pip install -r requirements.txt
```

Prefer `pip install -e .` when possible because it installs the project itself as an editable package.

The repository contains both `pyproject.toml` and `requirements.txt`.

---

# 8. Important dependency issue: Click/Typer

If the CLI produces an error involving Typer/Click incompatibility, use:

```powershell
pip install "click==8.1.8"
```

Then verify:

```powershell
workbench --help
```

You should see the CLI help.

---

# 9. Environment configuration

The repository contains `.env.example`.

Copy it:

```powershell
Copy-Item .env.example .env
```

For the basic local setup, use:

```env
PUBLIC_API_BASE=http://127.0.0.1:8000

ARTIFACTORY_URL=
ARTIFACTORY_REPO=
ARTIFACTORY_USER=
ARTIFACTORY_TOKEN=

RAG_EMBEDDING_MODEL_ID=

ALLOW_HF_DOWNLOAD=false
ALLOW_RAW_WORKFLOW=false

QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333

LIFECYCLE_POLL_INTERVAL_S=60
MODEL_DEFAULT_TTL_S=600
```

### Important

Do **not** put real API keys in `.env` or commit them to Git.

The current implementation uses the database-backed API-key system rather than the `ADMIN_TOKENS`/`USER_TOKENS` shown in the older setup document.

The current `.env.example` contains the actual configuration knobs used by this version, including Artifactory, RAG embedding model, HF-download policy, Qdrant and lifecycle settings.

---

# 10. Two different API-base environment variables

This is important.

The server uses:

```env
PUBLIC_API_BASE=http://127.0.0.1:8000
```

but the **CLI** uses:

```powershell
$env:WORKBENCH_API_BASE="http://127.0.0.1:8000"
```

Therefore, after opening a terminal where you want to use the CLI:

```powershell
$env:WORKBENCH_API_BASE="http://127.0.0.1:8000"
```

Do not assume `PUBLIC_API_BASE` automatically configures the CLI.

---

# 11. Qdrant

Qdrant is the vector database used by the RAG subsystem.

The repository expects:

```text
Qdrant host: 127.0.0.1
Qdrant port: 6333
```

The project can use a native Qdrant process rather than Docker.

Official Qdrant repository:

[Qdrant GitHub](https://github.com/qdrant/qdrant?utm_source=chatgpt.com)

Official releases:

[Qdrant releases](https://github.com/qdrant/qdrant/releases?utm_source=chatgpt.com)

---

# 12. Native Qdrant on Windows

The project launcher expects the Qdrant binary at:

```text
bin/qdrant.exe
```

Place the binary there.

Verify:

```powershell
Test-Path .\bin\qdrant.exe
```

Expected:

```text
True
```

The launcher starts Qdrant using:

```text
qdrant --config-path config/qdrant.yaml
```

Add `bin` to the current terminal's PATH:

```powershell
$env:Path="$PWD\bin;$env:Path"
```

Verify:

```powershell
Get-Command qdrant
```

---

# 13. Starting the bare-metal stack

From the project root:

```powershell
workbench up
```

Expected:

```text
Launcher: bare  Profile: small
qdrant started (...)
gateway started (...)
Bare-process stack started
```

The bare launcher starts:

```text
Qdrant
FastAPI gateway
```

The inference backend is started when required by the model lifecycle.

---

# 14. Bootstrap the administrator

On a fresh database, create the database/bootstrap administrator.

First make sure the stack is running.

Then:

```powershell
workbench admin bootstrap
```

This produces a one-time bootstrap admin API key.

### SECURITY

Save it securely.

Do **not**:

* commit it
* put it in GitHub
* put it in `.env`
* paste it into Discord
* put it in screenshots
* put it into the team repository

If it is exposed, revoke/rotate it.

---

# 15. Create a normal USER API key

The administrator should create separate keys for users.

Example:

```powershell
workbench admin keys create --owner teammate-name --scope user
```

The output contains the user API key.

That key should be given to the client application/Hermes.

### Do not give Hermes the admin key.

The intended separation is:

```text
ADMIN KEY
   │
   ├── register models
   ├── manage models
   ├── administrative operations
   └── configuration operations

USER KEY
   │
   ├── list models
   ├── chat
   ├── embeddings
   └── allowed inference/RAG operations
```

The repository describes this RBAC separation in its README.

---

# 16. Configure the client terminal

For a normal user:

```powershell
$env:WORKBENCH_API_BASE="http://127.0.0.1:8000"
$env:WORKBENCH_API_KEY="YOUR_USER_KEY"
```

Never write the real key into the documentation.

---

# 17. Test the gateway before touching models

Run:

```powershell
workbench status
```

Expected general structure:

```text
Status: ok
GPU 0 Used ...
Total ...
Loaded models: [...]
```

Then:

```powershell
workbench models list
```

---

# 18. Local model — no Artifactory

This is the easiest development configuration.

Put a GGUF model in:

```text
models/
```

Example:

```text
models/
└── Qwen_Qwen3.5-4B-Q4_K_M.gguf
```

The model does NOT have to be downloaded by the server if it is already present locally.

---

# 19. Example: Qwen3.5-4B GGUF

The exact model we successfully tested was:

```text
Qwen_Qwen3.5-4B-Q4_K_M.gguf
```

Download source used during validation:

[Qwen3.5-4B official Hugging Face model page](https://huggingface.co/Qwen/Qwen3.5-4B?utm_source=chatgpt.com)

GGUF source used during validation:

[Qwen3.5-4B GGUF repository](https://huggingface.co/bartowski/Qwen_Qwen3.5-4B-GGUF?utm_source=chatgpt.com)

For a 6 GB GPU, the Q4_K_M GGUF used in validation was approximately 2.8 GiB on disk and was registered with a VRAM estimate of approximately 4500 MB.

---

# 20. llama.cpp

For GGUF inference, llama.cpp provides the actual inference engine.

Official repository/releases:

[llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases/?utm_source=chatgpt.com)

For Windows NVIDIA GPU systems, choose:

```text
Windows x64 — CUDA 13
```

The official releases provide Windows x64 CUDA packages, including CUDA 13 builds and corresponding CUDA runtime DLL packages.

---

# 21. Windows llama.cpp installation

The validated setup used the Windows CUDA 13 package.

The release contained:

```text
llama-server.exe
ggml.dll
ggml-base.dll
ggml-cuda.dll
...
```

The CUDA runtime package contained:

```text
cublas64_13.dll
cublasLt64_13.dll
cudart64_13.dll
```

Put the relevant files into:

```text
bin/
```

The important executable is:

```text
bin/llama-server.exe
```

Verify:

```powershell
Test-Path .\bin\llama-server.exe
```

Then:

```powershell
$env:Path="$PWD\bin;$env:Path"
```

Verify:

```powershell
Get-Command llama-server
```

---

# 22. Test llama-server directly

Before debugging the Workbench, always prove the underlying inference engine works.

```powershell
.\bin\llama-server.exe `
  --model ".\models\Qwen_Qwen3.5-4B-Q4_K_M.gguf" `
  --port 5800 `
  --n-gpu-layers 99
```

You should eventually see:

```text
model loaded
listening on http://127.0.0.1:5800
```

If this fails, **do not debug the Workbench yet**.

Fix llama.cpp/GPU/model loading first.

---

# 23. Qwen3.5 thinking mode

This is an important Qwen3.5-specific issue discovered during validation.

A normal request with:

```json
"max_tokens": 100
```

may spend the entire token budget in reasoning.

The response can therefore look like:

```json
{
  "content": "",
  "reasoning_content": "..."
}
```

This does NOT necessarily mean inference failed.

For short normal chat responses, use:

```json
"chat_template_kwargs": {
    "enable_thinking": false
}
```

Example:

```json
{
  "model": "Qwen3.5-4B",
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
}
```

Our validated result was:

```text
Hello!
```

---

# 24. Direct llama-server test using PowerShell

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

---

# 25. Direct llama-server test using REAL curl

On Linux/macOS:

```bash
curl http://127.0.0.1:5800/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen3.5-4B",
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

On Windows, `curl.exe` avoids PowerShell's `curl` alias:

```powershell
curl.exe http://127.0.0.1:5800/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d "{\"model\":\"Qwen3.5-4B\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello in one short sentence.\"}],\"max_tokens\":100,\"chat_template_kwargs\":{\"enable_thinking\":false}}"
```

---

# 26. llama-swap

llama-swap sits between the Workbench and llama-server.

Architecture:

```text
Workbench
   │
   ▼
llama-swap :8100
   │
   ├── model A → llama-server :PORT
   ├── model B → llama-server :PORT
   └── model C → llama-server :PORT
```

Official project:

[llama-swap GitHub](https://github.com/mostlygeek/llama-swap?utm_source=chatgpt.com)

Official releases:

[llama-swap releases](https://github.com/mostlygeek/llama-swap/releases?utm_source=chatgpt.com)

---

# 27. Important llama-swap compatibility warning

This is currently the most important handoff warning.

The Workbench repository's llama-swap backend was written against an older llama-swap interface.

The current llama-swap build we tested was:

```text
v255
```

and its CLI expects:

```text
--listen
```

rather than the old:

```text
--port
```

Additionally, current llama-swap configuration uses a `cmd` containing `${PORT}`, for example:

```yaml
models:
  qwen3.5-4b:
    cmd: llama-server --port ${PORT} --model "..."
```

Current llama-swap documentation/discussions confirm that `${PORT}` is intended to be supplied through the model command.

Therefore:

**Do not blindly download an arbitrary newest llama-swap binary and assume it is compatible with the current Workbench backend.**

For a production/team handoff, either:

1. pin the llama-swap version known to match the repository implementation, or
2. update the Workbench llama-swap adapter to the current llama-swap interface.

For the validated manual stack, llama-swap v255 successfully loaded and routed the Qwen model.

---

# 28. Validated llama-swap configuration

For current llama-swap versions using the `cmd` configuration style:

```yaml
models:
  qwen3.5-4b:
    cmd: llama-server --port ${PORT} --model "C:\PATH\TO\Summertime-server\models\Qwen_Qwen3.5-4B-Q4_K_M.gguf"
```

The exact path must match the machine.

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

---

# 29. Start llama-swap manually

```powershell
$env:Path="$PWD\bin;$env:Path"
```

Then:

```powershell
.\bin\llama-swap.exe `
  --config .\config\llama-swap.yaml `
  --listen 127.0.0.1:8100
```

Expected:

```text
llama-swap listening on http://127.0.0.1:8100
```

---

# 30. Test llama-swap

In another terminal:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8100/v1/models" `
  -Method Get | ConvertTo-Json -Depth 10
```

Expected model:

```text
qwen3.5-4b
```

Initially it may say:

```text
status: unloaded
```

That is normal.

---

# 31. Trigger lazy model loading

Send:

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

$r = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8100/v1/chat/completions" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body

$r.choices[0].message.content
```

Expected:

```text
Hello!
```

At this point you have proved:

```text
llama-swap
      ↓
llama-server
      ↓
Qwen3.5 GGUF
      ↓
CUDA
      ↓
NVIDIA GPU
```

---

# 32. Registering the model with Workbench

The Workbench maintains a model registry in SQLite.

CLI:

```powershell
workbench models add --help
```

The relevant options are:

```text
name
--source
--backend
--type
--task
--pinned
--vram-mb
```

Example:

```powershell
workbench models add qwen3.5-4b `
  --source ".\models\Qwen_Qwen3.5-4B-Q4_K_M.gguf" `
  --backend llamaswap `
  --type text `
  --task chat `
  --vram-mb 4500
```

If the model is already registered:

```text
Error 409: Model 'qwen3.5-4b' already registered
```

Do **not** register it again.

Check:

```powershell
workbench models list
```

---

# 33. What `vram-mb` means

This is a reservation/estimate used by the lifecycle manager.

For the validated RTX 3050 6 GB system:

```text
Qwen3.5-4B Q4_K_M
vram estimate = 4500 MB
```

This is not simply the size of the GGUF file.

The model can occupy additional VRAM because of:

* KV cache
* CUDA buffers
* context size
* runtime allocations
* batch size

Therefore, don't automatically set:

```text
vram_mb = file size
```

Use a conservative estimate.

---

# 34. Workbench gateway

Once the gateway is running:

```text
http://127.0.0.1:8000
```

For another machine on the same LAN, the gateway must be reachable through the host's LAN IP, e.g.:

```text
http://192.168.1.50:8000
```

The server itself binds to:

```text
0.0.0.0:8000
```

so the operating-system firewall becomes important for remote access.

---

# 35. Local-only vs LAN access

## Local-only

Use:

```text
http://127.0.0.1:8000
```

Only the same machine can access it.

## LAN

Use:

```text
http://<SERVER-LAN-IP>:8000
```

Example:

```text
http://192.168.1.50:8000
```

Allow TCP port 8000 through the firewall if required.

Do NOT expose port 8000 directly to the public internet without proper TLS/reverse proxy/security controls.

---

# 36. Hermes integration

This is the intended client architecture.

The Workbench exposes an OpenAI-compatible endpoint.

Therefore Hermes should conceptually be configured as:

```text
Base URL:
http://SERVER_IP:8000/v1

API Key:
<USER API KEY>

Model:
qwen3.5-4b
```

The important point is:

**Use the Workbench USER API key, not the admin key.**

Hermes then sends something equivalent to:

```http
POST http://SERVER_IP:8000/v1/chat/completions
Authorization: Bearer <USER_API_KEY>
Content-Type: application/json
```

with:

```json
{
  "model": "qwen3.5-4b",
  "messages": [
    {
      "role": "user",
      "content": "Hello"
    }
  ]
}
```

If Hermes has a field called:

```text
OpenAI Compatible Base URL
```

put:

```text
http://SERVER_IP:8000/v1
```

not:

```text
http://SERVER_IP:8000/v1/chat/completions
```

The client should append `/chat/completions`.

---

# 37. Test the actual Workbench OpenAI-compatible API

This is the most important final test.

Set:

```powershell
$env:WORKBENCH_API_BASE="http://127.0.0.1:8000"
$env:WORKBENCH_API_KEY="YOUR_USER_KEY"
```

Then:

```powershell
curl.exe http://127.0.0.1:8000/v1/chat/completions `
  -H "Authorization: Bearer YOUR_USER_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"model\":\"qwen3.5-4b\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello in one short sentence.\"}],\"max_tokens\":100,\"chat_template_kwargs\":{\"enable_thinking\":false}}"
```

The expected response should contain:

```json
"content": "Hello!"
```

or an equivalent short response.

---

# 38. If the API is being called from another machine

Suppose the server machine has:

```text
192.168.1.50
```

Then from the teammate's machine:

```bash
curl http://192.168.1.50:8000/v1/chat/completions \
  -H "Authorization: Bearer <USER_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.5-4b",
    "messages": [
      {
        "role": "user",
        "content": "Say hello."
      }
    ],
    "max_tokens": 100,
    "chat_template_kwargs": {
      "enable_thinking": false
    }
  }'
```

If this works, Hermes can use exactly the same endpoint.

---

# 39. Artifactory configuration

Artifactory is optional for development.

## Without Artifactory

Models are manually placed into:

```text
models/
```

and registered using:

```text
source = local_path
```

This is the simplest configuration.

---

## With Artifactory

Set:

```env
ARTIFACTORY_URL=http://artifactory.internal/artifactory
ARTIFACTORY_REPO=models
ARTIFACTORY_USER=<username>
ARTIFACTORY_TOKEN=<token>
```

The repository's `.env.example` explicitly supports these Artifactory fields.

The intended architecture is:

```text
                Internal network

        ┌────────────────────────┐
        │       Artifactory      │
        │     private models     │
        └───────────┬────────────┘
                    │
                 download
                    │
                    ▼
        ┌────────────────────────┐
        │   Workbench Gateway    │
        └───────────┬────────────┘
                    │
                    ▼
              Local model
                    │
                    ▼
                Backend
```

This is appropriate for genuinely air-gapped environments where models are mirrored into internal storage.

---

# 40. Artifactory model registration

For an Artifactory-backed model, the API payload follows this structure:

```json
{
  "name": "llama-3-8b-instruct",
  "source": {
    "type": "artifactory",
    "path": "llm/llama-3-8b-instruct"
  },
  "backend": "vllm",
  "type": "text",
  "task_tags": [
    "chat",
    "coding"
  ],
  "vram_mb": 16000,
  "pinned": false
}
```

The repository's current setup document gives this model-registration structure.

Using the CLI, the source is passed with:

```text
--source
```

and the CLI determines whether it is a local path, HF source or Artifactory path.

---

# 41. Air-gapped mode

For a genuinely air-gapped installation:

```env
ALLOW_HF_DOWNLOAD=false
```

Keep:

```env
ARTIFACTORY_URL=<internal Artifactory>
ARTIFACTORY_REPO=<internal repository>
```

All required artifacts should already exist inside the network.

This includes:

```text
Python packages
Inference binaries
Model files
Embedding models
Qdrant binary
llama.cpp binaries
```

Do not assume an air-gapped machine can run:

```text
pip install ...
```

unless the Python packages have already been mirrored internally.

A real air-gapped deployment therefore needs an **offline artifact staging step**.

---

# 42. RAG — optional

RAG is optional.

You can run the Workbench perfectly well without RAG.

Without RAG:

```env
RAG_EMBEDDING_MODEL_ID=
```

Qdrant can still run because the bare launcher starts it, but you do not need to populate a RAG collection.

---

# 43. RAG architecture

When RAG is enabled:

```text
                 User query
                     │
                     ▼
              Workbench /rag/query
                     │
                     ▼
              Embedding model
                     │
                     ▼
                  vector
                     │
                     ▼
                 Qdrant
                     │
                     ▼
               top-k chunks
```

The current implementation exposes:

```text
POST /v1/rag/ingest
POST /v1/rag/query
```

and uses Qdrant as the backing vector database.

---

# 44. RAG requires an embedding model

This is critical.

Do NOT assume your chat model automatically works as an embedding model.

Set:

```env
RAG_EMBEDDING_MODEL_ID=<registered-embedding-model>
```

The model must be registered in the Workbench database.

The RAG implementation looks up the model by this ID and then calls the backend's embedding endpoint. Supported backends in the current implementation are:

```text
vllm
llamaswap
```

---

# 45. RAG embedding model requirements

The embedding model must support:

```text
/v1/embeddings
```

Example conceptual model:

```text
embedding-model
    ↓
POST /v1/embeddings
    ↓
vector
    ↓
Qdrant
```

Choose the embedding model according to your hardware and deployment constraints.

For an air-gapped environment, download the embedding model beforehand and place/mirror it internally.

---

# 46. Qdrant RAG configuration

Use:

```env
QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333
RAG_EMBEDDING_MODEL_ID=<your-embedding-model-id>
```

The current implementation creates a collection using cosine distance and stores:

```text
text
source
chunk_index
```

as payload.

---

# 47. RAG ingestion

The current RAG ingestion endpoint expects a **path on the server machine**.

It reads:

```python
Path(req.source_path)
```

and then:

```text
read text
→ split into chunks
→ embed chunks
→ write vectors to Qdrant
```

It is not a general-purpose PDF uploader/parser.

Therefore, for the current implementation, the safest input is a text file:

```text
.txt
```

or another file whose contents can be read as text.

The current implementation's source code confirms this behavior.

---

# 48. Example RAG ingest

Suppose:

```text
D:\knowledge\company.txt
```

exists on the **server**.

Call:

```bash
curl -X POST http://SERVER:8000/v1/rag/ingest \
  -H "Authorization: Bearer <USER_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "source_path": "D:\\knowledge\\company.txt"
  }'
```

The response should report the number of indexed chunks.

---

# 49. Query RAG

Example:

```bash
curl -X POST http://SERVER:8000/v1/rag/query \
  -H "Authorization: Bearer <USER_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the company leave policy?",
    "top_k": 5
  }'
```

The result contains retrieved chunks and similarity scores.

The current implementation returns:

```text
text
score
source
```

for each retrieved chunk.

---

# 50. RAG does NOT automatically mean "chat with documents"

An important architectural distinction:

```text
/v1/rag/query
```

retrieves relevant chunks.

It does not itself necessarily perform:

```text
retrieve
+
inject chunks into LLM prompt
+
generate answer
```

That orchestration belongs to the client/application layer unless another component performs it.

For Hermes, the higher-level client can perform:

```text
User question
      ↓
RAG query
      ↓
Retrieved context
      ↓
LLM prompt
      ↓
Workbench /v1/chat/completions
```

---

# 51. RAG without Artifactory

This is completely valid.

Use:

```text
Local embedding model
Local GGUF/chat model
Local Qdrant
Local Workbench
```

Example:

```text
models/
├── qwen3.5-4b.gguf
└── embedding-model/
```

and:

```env
ARTIFACTORY_URL=
RAG_EMBEDDING_MODEL_ID=my-embedding-model
```

---

# 52. RAG with Artifactory

Enterprise configuration:

```text
             Artifactory
             /        \
            /          \
       chat model    embedding model
            \          /
             \        /
              Workbench
                  │
                Qdrant
```

Both model artifacts can be maintained in the internal model repository.

This is the preferred architecture for a real sovereign/air-gapped installation.

---

# 53. Docker deployment

The repository includes Docker support.

Official Docker documentation:

[Docker Desktop](https://www.docker.com/products/docker-desktop/?utm_source=chatgpt.com)

For Linux:

```bash
docker compose up -d --build
```

The repository's setup document describes Docker Compose as an available deployment mode.

For NVIDIA GPU access, the host must have the appropriate NVIDIA container runtime configuration.

---

# 54. When NOT to use Docker

For your current Windows development workflow, native/bare mode is simpler.

Use bare mode when:

```text
You want:
✓ easy debugging
✓ direct access to GPU binaries
✓ no Docker
✓ Windows development
✓ Kaggle/cloud notebook compatibility
```

Use Docker when:

```text
You want:
✓ isolation
✓ reproducibility
✓ deployment packaging
✓ secure sandboxing
```

---

# 55. Code execution sandbox

The project has a code execution subsystem.

The README describes:

```text
Production:
Docker + gVisor + network isolation

Demo/Kaggle:
restricted bare-metal subprocess fallback
```

For production deployment, do not treat bare-metal arbitrary code execution as equivalent to a containerized sandbox.

---

# 56. Daily startup — Windows native

After everything is installed, the normal sequence should be approximately:

### Terminal 1

```powershell
cd C:\path\to\Summertime-server
.\venv\Scripts\Activate.ps1
$env:Path="$PWD\bin;$env:Path"
$env:WORKBENCH_API_BASE="http://127.0.0.1:8000"
$env:WORKBENCH_API_KEY="YOUR_USER_KEY"

workbench up
```

Then:

```powershell
workbench status
```

---

# 57. If using manually controlled llama-swap

Terminal 2:

```powershell
cd C:\path\to\Summertime-server
.\venv\Scripts\Activate.ps1
$env:Path="$PWD\bin;$env:Path"

.\bin\llama-swap.exe `
  --config .\config\llama-swap.yaml `
  --listen 127.0.0.1:8100
```

Keep this terminal alive.

---

# 58. Final smoke test

Run:

```powershell
workbench status
```

Then:

```powershell
workbench models list
```

Then:

```powershell
curl.exe http://127.0.0.1:8000/v1/chat/completions `
  -H "Authorization: Bearer YOUR_USER_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"model\":\"qwen3.5-4b\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello in one short sentence.\"}],\"max_tokens\":100,\"chat_template_kwargs\":{\"enable_thinking\":false}}"
```

Success means:

```text
HTTP 200
+
choices[0].message.content is non-empty
```

---

# 59. What each layer proves

When debugging, test bottom-up.

## Test 1 — GPU

```powershell
nvidia-smi
```

If this fails:

```text
GPU/driver problem
```

---

## Test 2 — llama-server

```text
localhost:5800/v1/chat/completions
```

If this fails:

```text
llama.cpp/model/CUDA problem
```

---

## Test 3 — llama-swap

```text
localhost:8100/v1/chat/completions
```

If this fails:

```text
llama-swap/backend problem
```

---

## Test 4 — Workbench

```text
localhost:8000/v1/chat/completions
```

If this fails but llama-swap works:

```text
Workbench lifecycle/routing/auth/config problem
```

---

## Test 5 — remote client

```text
SERVER_IP:8000/v1/chat/completions
```

If localhost works but remote access fails:

```text
Firewall/network/binding problem
```

---

## Test 6 — Hermes

If curl from another machine works but Hermes doesn't:

```text
Hermes configuration problem
```

This layered debugging strategy prevents wasting hours debugging the wrong component.

---

# 60. Common problems

## `ModuleNotFoundError: sqlalchemy`

Run:

```powershell
pip install -e .
```

or:

```powershell
pip install -r requirements.txt
```

---

## Typer/Click error

Use:

```powershell
pip install "click==8.1.8"
```

---

## CLI says:

```text
WORKBENCH_API_KEY env var not set
```

Set:

```powershell
$env:WORKBENCH_API_KEY="YOUR_KEY"
```

---

## CLI tries:

```text
https://localhost:8000
```

but server is HTTP.

Set:

```powershell
$env:WORKBENCH_API_BASE="http://127.0.0.1:8000"
```

---

## `llama-swap binary not found`

Check:

```powershell
Test-Path .\bin\llama-swap
Test-Path .\bin\llama-swap.exe
```

The current Workbench launcher checks the path without the `.exe` suffix.

On Windows, if necessary, create a hardlink:

```powershell
cmd /c mklink /H bin\llama-swap bin\llama-swap.exe
```

Then:

```powershell
Test-Path .\bin\llama-swap
```

must return:

```text
True
```

---

# 61. llama-swap says `flag provided but not defined: -port`

This means the installed llama-swap version expects:

```text
--listen
```

rather than:

```text
--port
```

This is a **version compatibility issue**, not a GPU problem.

Do not randomly modify model files until you've identified the llama-swap version.

---

# 62. llama-swap says:

```text
proxy uses ${PORT} but cmd does not
```

Current llama-swap expects `${PORT}` to be used by the model command.

Example:

```yaml
cmd: llama-server --port ${PORT} --model "..."
```

This behavior is documented by the llama-swap maintainer.

---

# 63. llama-swap says:

```text
exec: "llama-server": executable file not found
```

Check:

```powershell
Get-Command llama-server
```

If it is not found:

```powershell
$env:Path="$PWD\bin;$env:Path"
```

Then:

```powershell
Get-Command llama-server
```

must resolve to:

```text
...\Summertime-server\bin\llama-server.exe
```

Restart llama-swap after changing PATH.

---

# 64. Qwen response has empty `content`

Inspect the raw response.

If you see:

```json
"content": "",
"reasoning_content": "..."
```

the model is thinking.

Use:

```json
"chat_template_kwargs": {
  "enable_thinking": false
}
```

and give it enough `max_tokens`.

---

# 65. HTTP 404:

```text
no router for requested model
```

Usually means llama-swap does not currently have a route for that model.

Check:

```powershell
Invoke-RestMethod `
  http://127.0.0.1:8100/v1/models
```

Look for:

```text
qwen3.5-4b
```

---

# 66. HTTP 500 from Workbench

Do not immediately blame the model.

Test in order:

```text
llama-server
    ↓
llama-swap
    ↓
Workbench
```

If llama-server succeeds and llama-swap succeeds, inspect the Workbench gateway logs/lifecycle manager.

---

# 67. Port 8000 already in use

Check:

```powershell
netstat -ano | findstr ":8000"
```

Only **one gateway** should own port 8000.

An API-key terminal is not a second server.

This distinction is important:

```text
Admin terminal ─────┐
                    │
User terminal ──────┼──→ SAME gateway :8000
                    │
Hermes ─────────────┘
```

API keys determine authorization; they do not create separate gateway instances.

---

# 68. Port 8100 already in use

Check:

```powershell
netstat -ano | findstr ":8100"
```

Only one llama-swap instance should own that port.

---

# 69. `workbench down` crashes on Windows

If the launcher encounters a Windows process termination error such as:

```text
WinError 87
```

do not interpret that as an inference failure.

It is a process-management issue in the shutdown path.

You can inspect running processes:

```powershell
Get-Process qdrant,llama-swap,llama-server `
  -ErrorAction SilentlyContinue
```

and inspect ports:

```powershell
netstat -ano | findstr ":8000"
netstat -ano | findstr ":8100"
netstat -ano | findstr ":6333"
```

---

# 70. Model already registered

If:

```text
409 Model already registered
```

simply run:

```powershell
workbench models list
```

Do not add it repeatedly.

---

# 71. RAG says:

```text
rag_embedding_model_id not configured
```

Set:

```env
RAG_EMBEDDING_MODEL_ID=<registered-model-id>
```

Restart the gateway.

---

# 72. RAG says embedding model is not registered

Run:

```powershell
workbench models list
```

and ensure the model ID exactly matches:

```env
RAG_EMBEDDING_MODEL_ID=
```

---

# 73. RAG embedding backend error

The current RAG implementation only proxies embeddings through supported embedding backends.

Make sure your registered embedding model actually provides:

```text
/v1/embeddings
```

A normal chat-only model should not automatically be assumed to be an embedding model.

---

# 74. Qdrant unavailable

Check:

```powershell
netstat -ano | findstr ":6333"
```

and:

```powershell
Invoke-RestMethod http://127.0.0.1:6333/collections
```

If Qdrant is not running, start the bare stack again.

---

# 75. Production network recommendation

Do not expose:

```text
8000
8100
8200
8300
6333
```

to the public internet.

Recommended:

```text
                    LAN
                     │
                     ▼
               Reverse Proxy
                  :443
                     │
                     ▼
              Workbench :8000
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
   llama-swap      vLLM        Qdrant
   localhost       localhost   localhost
```

The inference engines and Qdrant should normally remain bound to localhost/private interfaces.

Only expose the API gateway.

---

# 76. Security model for Hermes

Hermes should receive:

```text
USER API KEY
```

not:

```text
ADMIN API KEY
```

The client should know:

```text
Base URL
API key
Model ID
```

The client should NOT know:

```text
Artifactory credentials
database credentials
admin API key
internal backend ports
```

---

# 77. Minimal development configuration

For a teammate who simply wants to get a local LLM running:

```text
Git
Python
NVIDIA driver
Qdrant binary
llama.cpp CUDA binaries
llama-swap
GGUF model
Python dependencies
```

Configuration:

```env
PUBLIC_API_BASE=http://127.0.0.1:8000

ARTIFACTORY_URL=
ARTIFACTORY_REPO=
ARTIFACTORY_USER=
ARTIFACTORY_TOKEN=

RAG_EMBEDDING_MODEL_ID=

ALLOW_HF_DOWNLOAD=false
ALLOW_RAW_WORKFLOW=false

QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333
```

Then:

```text
workbench up
        ↓
register model
        ↓
start/test llama-swap
        ↓
curl /v1/chat/completions
```

---

# 78. Enterprise configuration

For the real air-gapped deployment:

```text
                    Enterprise LAN
                         │
                ┌────────▼────────┐
                │ Internal Proxy  │
                │      :443       │
                └────────┬────────┘
                         │
                ┌────────▼────────┐
                │    Workbench    │
                │     :8000       │
                └───┬─────────┬───┘
                    │         │
                    │         │
             ┌──────▼───┐ ┌──▼───────────┐
             │ Artifactory│ │   Qdrant    │
             │  internal │ │   :6333     │
             └───────────┘ └──────────────┘
                    │
                    ▼
              Model artifacts
                    │
                    ▼
          Local inference backends
```

Set:

```env
ARTIFACTORY_URL=<internal URL>
ARTIFACTORY_REPO=<internal repository>
ARTIFACTORY_USER=<service account>
ARTIFACTORY_TOKEN=<secret>
ALLOW_HF_DOWNLOAD=false
```

This is the intended sovereign/air-gapped deployment model described by the project.

---

# 79. Final handoff checklist

A teammate should not say "it works" until all applicable checks pass.

## Host

```text
[ ] Git installed
[ ] Python installed
[ ] NVIDIA driver installed if GPU required
[ ] nvidia-smi works
```

## Python

```text
[ ] venv created
[ ] venv activated
[ ] pip install -e .
[ ] workbench --help works
```

## Infrastructure

```text
[ ] Qdrant installed
[ ] Qdrant :6333 reachable
[ ] llama-server installed
[ ] llama-swap installed
```

## Model

```text
[ ] GGUF present
[ ] llama-server can load it
[ ] GPU is actually used
[ ] direct /v1/chat/completions works
```

## Workbench

```text
[ ] database initialized
[ ] bootstrap admin created
[ ] user API key created
[ ] WORKBENCH_API_BASE configured
[ ] WORKBENCH_API_KEY configured
[ ] workbench status works
[ ] model registered
```

## Final API

```text
[ ] /v1/models works
[ ] /v1/chat/completions works
[ ] authentication works
[ ] user key works
[ ] admin key is NOT used by Hermes
```

## RAG, if enabled

```text
[ ] Qdrant works
[ ] embedding model registered
[ ] RAG_EMBEDDING_MODEL_ID configured
[ ] /v1/rag/ingest works
[ ] /v1/rag/query works
```

## Remote/Hermes

```text
[ ] server reachable over LAN
[ ] port 8000 allowed
[ ] curl from another machine works
[ ] Hermes base URL ends in /v1
[ ] Hermes uses USER API key
[ ] Hermes model name matches registered model ID
```

---

# 80. The 5-minute validation procedure

Once a teammate has already installed everything, the fastest sanity test is:

### Terminal 1

```powershell
cd C:\path\to\Summertime-server
.\venv\Scripts\Activate.ps1

$env:Path="$PWD\bin;$env:Path"
$env:WORKBENCH_API_BASE="http://127.0.0.1:8000"
$env:WORKBENCH_API_KEY="USER_KEY"

workbench up
```

### Terminal 2

```powershell
workbench status
workbench models list
```

### Terminal 3

If using the validated manual llama-swap setup:

```powershell
$env:Path="$PWD\bin;$env:Path"

.\bin\llama-swap.exe `
  --config .\config\llama-swap.yaml `
  --listen 127.0.0.1:8100
```

### Terminal 4

```powershell
curl.exe http://127.0.0.1:8000/v1/chat/completions `
  -H "Authorization: Bearer USER_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"model\":\"qwen3.5-4b\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello in one short sentence.\"}],\"max_tokens\":100,\"chat_template_kwargs\":{\"enable_thinking\":false}}"
```

If the response contains:

```text
Hello!
```

the core system is operational.

---

# 81. What should be committed to the team repository

Commit:

```text
config/
server/
tests/
ui/
pyproject.toml
requirements.txt
docker-compose.yml
.env.example
SETUP.md
README.md
```

Do NOT commit:

```text
.env
data/workbench.db
API keys
Artifactory tokens
private certificates
large model files
personal credentials
```

For large model/binary artifacts, use your organization's artifact storage/release system instead of Git.

---

# 82. Recommended team artifact bundle

For genuinely painless handoff, the team should eventually maintain:

```text
Summertime-server/
│
├── server/
├── config/
├── tests/
├── ui/
│
├── bin/
│   ├── qdrant.exe
│   ├── llama-swap.exe
│   ├── llama-server.exe
│   ├── ggml*.dll
│   ├── cublas64_13.dll
│   ├── cublasLt64_13.dll
│   └── cudart64_13.dll
│
├── models/
│   └── <model files>
│
├── data/
│
├── .env.example
├── requirements.txt
├── pyproject.toml
└── SETUP.md
```

For an air-gapped deployment, the `bin/` and model artifacts should be distributed through an approved internal artifact mechanism.

---

# 83. Final architecture

Once everything is operational:

```text
                          ┌──────────────────┐
                          │     Hermes       │
                          │ OpenAI client    │
                          └────────┬─────────┘
                                   │
                          Bearer USER API KEY
                                   │
                                   ▼
                     ┌─────────────────────────┐
                     │  Workbench FastAPI      │
                     │        :8000             │
                     │                         │
                     │ RBAC                    │
                     │ Lifecycle Manager       │
                     │ Model Registry          │
                     │ OpenAI API              │
                     │ RAG API                 │
                     └───────┬─────────┬───────┘
                             │         │
                 inference   │         │ RAG
                             │         │
                             ▼         ▼
                      ┌──────────┐  ┌──────────┐
                      │ llama-   │  │ Qdrant   │
                      │ swap     │  │  :6333   │
                      │ :8100    │  └────┬─────┘
                      └────┬─────┘       │
                           │              │
                           ▼              │
                    ┌─────────────┐       │
                    │ llama-      │       │
                    │ server      │       │
                    └──────┬──────┘       │
                           │              │
                           ▼              │
                    ┌─────────────┐       │
                    │ Qwen GGUF   │       │
                    └──────┬──────┘       │
                           │              │
                           ▼              │
                         GPU ◄────────────┘
```

The Workbench is therefore the **single API surface** that Hermes needs to know about.

Hermes should not directly talk to llama-server, Qdrant, Artifactory, or the database.

---

# 84. One final warning for whoever maintains this

There are two things that should eventually be pinned in the project's release documentation:

### 1. llama.cpp version

Do not say:

```text
download latest llama.cpp
```

Say:

```text
use the tested llama.cpp build
```

because inference binaries can change behavior.

### 2. llama-swap version

This is even more important.

The current Workbench adapter and the current llama-swap CLI/configuration have an interface mismatch.

Therefore the team should eventually make one explicit decision:

```text
OPTION A:
Pin a llama-swap version compatible with this Workbench commit.

OR

OPTION B:
Update the Workbench llama-swap adapter to the current llama-swap API.
```

Do not leave this as "install the latest llama-swap."

That single sentence will save the next teammate potentially **hours of debugging**.

---

# 85. Official external resources

### Workbench

[Summertime-server repository](https://github.com/Artyfowl1710/Summertime-server?utm_source=chatgpt.com)

### Git

[Git for Windows](https://gitforwindows.org/?utm_source=chatgpt.com)

### Python

[Python downloads](https://www.python.org/downloads/?utm_source=chatgpt.com)

### NVIDIA

[NVIDIA drivers](https://www.nvidia.com/Download/index.aspx?utm_source=chatgpt.com)

### llama.cpp

[llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases/?utm_source=chatgpt.com)

### llama-swap

[llama-swap releases](https://github.com/mostlygeek/llama-swap/releases?utm_source=chatgpt.com)

### Qdrant

[Qdrant releases](https://github.com/qdrant/qdrant/releases?utm_source=chatgpt.com)

### Qwen3.5

[Qwen3.5 official model](https://huggingface.co/Qwen/Qwen3.5-4B?utm_source=chatgpt.com)

### Qwen3.5 GGUF used during validation

[Qwen3.5-4B GGUF](https://huggingface.co/bartowski/Qwen_Qwen3.5-4B-GGUF?utm_source=chatgpt.com)

### Docker

[Docker Desktop](https://www.docker.com/products/docker-desktop/?utm_source=chatgpt.com)

---

## Bottom line

For a teammate, the conceptual setup should be:

```text
1. Install Python/Git/NVIDIA driver
2. Clone repo
3. Create venv
4. pip install -e .
5. Install Qdrant
6. Install llama.cpp CUDA binaries
7. Install compatible llama-swap
8. Put GGUF in models/
9. Configure .env
10. Start Qdrant + gateway
11. Bootstrap admin
12. Create USER API key
13. Register model
14. Test llama-server
15. Test llama-swap
16. Test Workbench /v1/chat/completions
17. Put http://SERVER_IP:8000/v1 into Hermes
18. Put USER API key into Hermes
19. Set model = qwen3.5-4b
20. Done.
```

**RAG is an optional second layer**:

```text
embedding model
      ↓
Qdrant
      ↓
/v1/rag/ingest
/v1/rag/query
```

**Artifactory is an optional deployment/storage layer**:

```text
Artifactory
      ↓
Workbench
      ↓
local inference
```

So the smallest working deployment is actually quite simple; Artifactory + RAG + multiple backends are progressively added layers rather than prerequisites for basic OpenAI-compatible inference.

The repository's own README confirms that the gateway is designed specifically to expose OpenAI-compatible inference while supporting llama-swap, vLLM, ONNX Runtime, ComfyUI, RAG/Qdrant, lifecycle management and RBAC.
