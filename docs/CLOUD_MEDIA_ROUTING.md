# Cloud media routing and self-hosted servers

Use the native desktop's **Runtime** page to add a provider key or connect your own OpenAI-compatible server. **Change model** discovers the provider's full model list. Google discovery uses its native paginated Models API and the saved Google credential, rather than assuming an OpenAI response format.

The picker and model cards distinguish text-only, multimodal, image, video, audio and specialist capabilities. Missing metadata is labeled unknown. Google Live, TTS, image-generation and embedding entries stay visible but cannot accidentally become ordinary chat models. Their presence in a quota table does not implement their specialist API workflows. Search/map grounding quotas describe provider tools, not additional model IDs.

## Image and video policy

- In `agent.image_input_mode: auto`, an explicitly assigned `auxiliary.vision` reader takes priority. Otherwise a capable selected main receives the image directly. Explicit `native` or `text` mode remains the final user override; `provider: auto, model: auto` means inherit, not a specialist assignment.
- A text-only main uses an explicitly configured vision reader when present. Otherwise Google/OpenRouter compare compatible readers on the same provider using known published input/output token prices. The estimate assumes 1,000 input and 300 output tokens. Unknown prices are excluded from automatic cost ranking; they are not assumed free. This is not an account-specific free-tier or media-billing quote.
- A model must support every required input modality and text output. Image-only OCR is never selected for video. An explicit video tool model or `auxiliary.video` assignment wins; otherwise a selected video-capable main handles video. A model-only video override is validated against video capability before use.
- Video uses its own task configuration, endpoint, credential reference, timeout and temperature. It does not inherit `auxiliary.vision` or `AUXILIARY_VISION_MODEL`. A missing explicitly referenced video key stops before inference. For self-hosted video, declare video/text modalities or assign a video specialist explicitly; an unknown server is not assumed capable.
- Cloud vision requests preserve the live session's provider key and endpoint when choosing another model. Failures do not silently switch to another provider/account.
- If an automatically selected image reader returns a model-specific 404, try at most two other compatible readers. Remember the unavailable reader for ten minutes in memory, scoped to profile, provider, endpoint and credential fingerprint. Explicit reader and main-model choices surface their error. Quota/payment errors are not invitations to spend on another account.
- Media tool results include `routing.provider` and `routing.model`. Auto Routing offers a capability/price preview; it does not make a generation request or verify quota.

Google listings are cached for ten minutes with up to three days of stale data on discovery failure. Refresh Models forces discovery. Credential/endpoint rotation invalidates that cache. Cache files contain public model metadata and credential fingerprints, never raw API keys.

The Google native adapter now preserves bounded inline image, video and audio payloads. This does not replace the separate voice transcription/Live API workflows. Audio payload conversion has contract coverage; live audio/Live/TTS/image-generation acceptance is not claimed here.

## Connect your own server

In **Runtime → Connect your own model server**, enter a name, API base URL and model ID. **Test connection** reads `/models` and fills model suggestions; it does not make a generation call. Declare only modalities supported by both the loaded model and server.

| Server | Typical API base | Key |
| --- | --- | --- |
| Ollama on this PC | `http://127.0.0.1:11434/v1` | Normally blank |
| llama.cpp on this PC | `http://127.0.0.1:8080/v1` | Blank unless the server was configured with a key |
| Protected remote OpenAI-compatible server | Its HTTPS base ending in `/v1` | Key supplied by its operator |

The key field is optional. Saving a nonempty key writes it through the existing profile `.env` secret reference; it is not written into `config.yaml`. Blank input from the new form preserves an existing key. The endpoint is only selected as main when the corresponding checkbox is checked. Start a new conversation after changing the main model.

## Verified on 31 October 2026

These are historical live-service checks. The 1 November precedence correction below supersedes the earlier behavior that ignored an assigned image reader.

Using the existing saved Google key and synthetic media only:

- Native agent image recognition with `gemini-3.5-flash-lite`: passed with an unavailable local reader configured, proving the capable main retained the image.
- Explicit cloud auxiliary image reader: passed.
- Unpinned cheapest compatible image reader: passed. Google listed `gemini-2.5-flash-lite` but rejected generation as unavailable to new users; recovery selected `gemini-3.1-flash-lite` and read `INDRA42` correctly.
- Video tool on selected `gemini-3.5-flash-lite`: identified a synthetic blue clip correctly.
- Running desktop model-picker API: 60 Google IDs, including specialist entries and modality metadata.
- Native renderer: Google key dropdown, self-hosted form, image/video/audio labels, specialist label and prevention of accidental TTS-as-chat selection passed.

These checks establish the named routes, not all provider models or every quota entitlement. OpenRouter live generation still needs usable quota on its configured key. Local inference remains a separate previously verified route; the original SIH reference source was not edited.

References: [Google Models API](https://ai.google.dev/api/models), [Google rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), [Ollama authentication](https://docs.ollama.com/api/authentication), [llama.cpp server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server).

## Routing correction on 1 November 2026

Reproduced an explicit video endpoint being ignored whenever the primary advertised video. Corrected explicit-reader precedence for both images and video, normalized the auto model sentinel and separated video configuration from image configuration throughout auxiliary resolution, transport adaptation and retry handling. An unavailable explicit media provider no longer falls into ambient provider discovery during initial resolution.

Real OpenAI SDK requests against a temporary loopback receiver verify the selected primary for default summarization/title/image auxiliary calls, independent image/video reader models and credentials, and rejection before inference when a referenced video credential is absent. These fixtures verify routing and payload transport, not cloud inference quality, microphone capture or actual video decoding. User runtime state and the SIH reference folder are untouched.
