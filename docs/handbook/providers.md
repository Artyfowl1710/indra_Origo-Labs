# Models, providers and routing


## Hosted models

Use Keys to add the provider's credential; use Models to select a model. The recorded configuration uses Baseten with `meta-models/muse-spark-open-1026`. OpenRouter and other configured providers have their own credentials and discovery endpoints. A provider's current model list, permissions, pricing and quotas are authoritative. A model appearing in a catalog does not guarantee account access or free usage.

Refresh the catalog after adding a key or changing an endpoint. Catalog caches reduce repeated discovery calls; stale entries can remain until refreshed. Capability labels distinguish text, image and other supported streams when provider metadata is available. Unknown metadata should not be treated as a confirmed capability.

## One multimodal model or specialist roles

A compatible multimodal model can handle its supported inputs directly. Otherwise configure the relevant specialist/auxiliary role, such as vision/OCR. The coding agent receives the specialist's extracted description; this is not the same as the coding model itself seeing the image. A text-only model cannot acquire vision by changing its name. Unsupported streams need an explicitly configured compatible provider/model or local vision runtime.

Automatic routing uses available configuration and capability information. User-selected roles take precedence; cost depends on provider metadata and actual billing. There is no promise that every unknown provider is routed optimally or that failed calls are free. Audit the selected model and provider after a run.

## Self-hosted Ollama or llama.cpp

Start your own compatible server separately. In the model/provider configuration select the local/custom OpenAI-compatible endpoint, for example `http://127.0.0.1:11434/v1` for Ollama's compatible API or your llama.cpp server's `/v1` URL. Discover/select a model that server actually serves. A local server usually has no API key unless you configured authentication; if your server requires one, enter its key, not an OpenRouter key. Do not expose an unauthenticated inference server on the internet.

The optional managed llama.cpp router needs its runtime directory, model weights and compatible vision projection configured; developer-machine paths are not portable defaults. Qwen coding and Qwen2-VL/OCR are separate roles when run as separate models. Large weights are excluded from this release.
