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

## Self-hosted vLLM with signed model releases

Use the local or custom OpenAI-compatible provider at `http://127.0.0.1:8100/v1`. Select the model name recorded in the approved manifest and enter the server's API key. This optional launcher runs on Linux, including a WSL installation where vLLM can use the GPU. Bundle verification also works on Windows. Install a vetted vLLM release and this repository's `cryptography` dependency in a dedicated Python environment. The launcher keeps the server on loopback.

Stage a complete local model snapshot with safetensors weights, configuration, tokenizer and any chat template. Use a clean directory with regular files and no links. On the release workstation, generate and review an exact inventory, then sign its bytes with the release authority's Ed25519 key. The following example uses OpenSSL 3. Keep all three approval files outside the model tree. Use byte-preserving redirection in a Linux shell for manifest generation.

```sh
python -m origo_runtime.verified_vllm manifest /path/to/staged-model \
  --model approved-model > manifest.json
openssl pkeyutl -sign -rawin -inkey release-private.pem -in manifest.json -out manifest.sig
```

On the serving host, pin the corresponding public key from a trusted source. Protect the mount path, trust key, and approved release files with operator-controlled permissions. Present the same model snapshot on a read-only mount whose backing storage the server account cannot modify, including through other paths. Mounting a writable source read-only for the server still requires protecting the source from writes. Run from the Indra checkout with `VLLM_API_KEY` in the environment.

```sh
python -m origo_runtime.verified_vllm verify /srv/indra/model \
  --manifest manifest.json --signature manifest.sig --trusted-key release-public.pem
python -m origo_runtime.verified_vllm serve /srv/indra/model \
  --manifest manifest.json --signature manifest.sig --trusted-key release-public.pem
```

The launcher refuses to start if the signature fails or a file is missing, changed, unsigned, or writable through the model mount. It starts vLLM with local weights and tokenizer, the safetensors loader, Hugging Face offline mode, and request logging disabled. Configure network policy separately if the host requires egress isolation. For a small GPU, adjust `--max-model-len` and `--gpu-memory-utilization` to fit the model and workload. `--enforce-eager` can reduce graph memory at the cost of performance on some workloads.

Save the startup event's manifest digest with deployment records. It records the release verified before launch. Request-level signed receipts and hardware runtime attestation require additional controls. Retire superseded manifests through the deployment policy so they cannot be selected for a new launch.

For capacity testing, [run vLLM's serving benchmark](https://docs.vllm.ai/en/latest/benchmarking/cli/) against the authenticated loopback endpoint. Use synthetic prompts at first. Keep the model digest and prompt and output lengths fixed when comparing concurrency limits. Record successful output tokens per second and p95 time to first token. For whole-server energy, read a node or wall energy meter over the same interval and divide joules by successful output tokens, then scale to 1,000 tokens. Label a measurement from GPU telemetry as GPU-only.
