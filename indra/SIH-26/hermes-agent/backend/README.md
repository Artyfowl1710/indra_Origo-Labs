# Air-Gapped AI Workbench

The **Air-Gapped AI Workbench** is an enterprise-grade, offline-first AI inference server and orchestration gateway. Designed for high-security environments, it operates with **zero outbound internet calls**, allowing organizations to run state-of-the-art Generative AI models (LLMs, VLMs, Diffusion Models) securely on-premises, on edge devices, or within isolated cloud environments.

## 🌟 Key Specialties & Value Proposition

### 1. 100% Air-Gapped & Offline-First
Everything from model fetching to inference execution happens within your secure perimeter. Models are securely pulled from your private internal Artifactory—no calls are made to HuggingFace, OpenAI, or any public internet services. 

### 2. Smart GPU VRAM Lifecycle Manager
The built-in intelligent Lifecycle Manager acts as a traffic controller for your GPUs:
- **Zero Out-of-Memory (OOM) Errors**: Automatically calculates VRAM requirements before loading models. 
- **LRU Eviction & Queuing**: If VRAM is full, idle models are automatically evicted (LRU) to make room. If all models are busy, requests are gracefully queued without dropping connections.
- **Concurrency Caps**: Limits the number of heavy vLLM processes to prevent system instability, queuing requests when capacity is reached.

### 3. Multi-Backend Orchestration Gateway
The server automatically routes requests to the optimal backend engine based on the registered model:
- **vLLM**: For ultra-fast, high-throughput LLM text generation and LoRA adapter serving.
- **ONNX Runtime**: For edge devices, CPU-only environments, and efficient cross-platform execution.
- **ComfyUI**: For advanced Image, Video, and Audio generation workflows.
- **Llama-swap**: For rapid prototyping and swapping of GGUF models.

### 4. Code Execution Sandbox
Built-in execution engine for AI-generated code (Python, JavaScript, Bash, R). 
- **Production Mode**: Uses Docker and gVisor with `--network none` and strict CPU/Memory resource limits for maximum security.
- **Demo/Kaggle Mode**: Falls back to restricted bare-metal subprocesses when Docker is unavailable.

### 5. OpenAI-Compatible API
Drop-in replacement for any application currently using OpenAI APIs. The gateway exposes standard `/v1/chat/completions` and `/v1/embeddings` endpoints, meaning your existing UI dashboards, LangChain agents, and internal tooling can switch to this secure workbench instantly without code changes.

### 6. Role-Based Access Control (RBAC)
Enforces strict authentication via API Keys. Differentiates between:
- **Admin**: Can register models, sync manifests, and access raw workflows.
- **User**: Can list models, generate text/images, and execute sandboxed code.

---

## 🏗️ Core Functionalities

- **Text Generation**: Streaming and non-streaming LLM inference.
- **Embeddings**: Vector embeddings for Retrieval-Augmented Generation (RAG) pipelines.
- **Multimodal Generation**: Image, Audio, and Video generation via ComfyUI backend integration.
- **LoRA Adapter Support**: Dynamically loads and unloads LoRA adapters on top of base vLLM models without taking down the base process.
- **Model Registry & Sync**: Declarative model manifest synchronization to easily deploy new model fleets across clusters.
- **Catalog Traversal**: Deep recursive scanning of private Artifactory repositories to discover available offline models.

---

## 🎯 Target Environments

The server is heavily optimized to scale up or down depending on the environment:
1. **On-Prem GPU Clusters**: Fully utilizes multiple GPUs with vLLM and ComfyUI for enterprise scale.
2. **Kaggle / Cloud Notebooks**: Graceful fallbacks for code sandboxing and VRAM heuristics when standard tools (`nvidia-smi`, `docker`) are restricted.
3. **Developer Laptops (Edge)**: Runs efficiently using ONNX or Llama-swap backends on CPU or consumer GPUs.

*(For installation and deployment instructions, refer to `SETUP.md`)*
