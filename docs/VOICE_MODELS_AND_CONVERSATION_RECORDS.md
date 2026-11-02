# Voice models and conversation records

Indra is built by Origo Labs. Open **Chat → Voice Mode** and choose a model in the generic **Model** selector. The currently connected native audio service provides the Gemini options. Keys stay on the backend; the renderer uses an authenticated [local Live voice bridge](LIVE_VOICE_BRIDGE.md). Quotas and session limits still apply.

## Add Baseten / Muse Spark Open

In Change model, choose **Add API key or model endpoint** (also available in Runtime), choose **Use Baseten · Muse Spark Open · Hackathon**, enter your Baseten key and save. The preset uses:

- Base URL: `https://inference.baseten.co/v1`
- Model: `meta-models/muse-spark-open-1026`
- **Offer this model in Voice mode** enabled

Reopen Voice Mode to refresh its selector. This connection uses audio input for transcription, the selected model for text reasoning with project Knowledge, and device speech for playback. It is a turn-based speech pipeline. Computer execution requires the coding agent and its existing approval controls.

The adapter follows [Baseten's model announcement](https://www.baseten.co/resources/changelog/muse-spark-open-and-nemotron-35-super-vl-available-on-baseten/) and [Meta's Baseten examples](https://github.com/meta-models/meta-oss-cookbook/blob/main/muse-spark/hosted/baseten.md). Muse Spark Open accepts audio input and returns text. Native bidirectional audio protocols require a dedicated adapter; an arbitrary OpenAI-compatible text endpoint does not become a native audio model automatically.

Contract tests cover the request shape, named connection selection and credential handling. A real Baseten request remains unverified until a working key is supplied. Device speech availability depends on the voices installed on the computer. Other enabled text endpoints use the configured transcription service when native audio transcription is unavailable.

## Document conversations and actions

**Save transcript and activity to this chat** is enabled by default in Voice Mode. Disable it before starting if you do not want new voice entries saved. Indra stores captured text locally, without raw audio recordings. A voice-only conversation is saved to Sessions after its first recorded activity.

In Chat, open **Settings → Conversation & export** to see the conversation record. Voice Mode shows a dismissible first-use notice pointing here. The record includes:

- Voice transcript with speaker and selected model.
- Local notes for call start/end, microphone controls, Knowledge lookups and handoff to the coding agent.
- Runtime observations of tool start/completion, approval responses and model changes, attributed to the chat and model.

Choose **Export conversation as Markdown** to download the current chat messages and the latest saved voice/action entries. Reopen the chat from Sessions to view its saved record. Records remain scoped to the active local profile in `workspace-data/conversation-records.sqlite3` beneath that profile's runtime directory. They are not uploaded or automatically inserted into the model's cached conversation history.

Runtime action entries are separate from client-authored transcript notes. The authenticated browser API cannot author `action` entries. The existing signed audit ledger stores hashes of event payloads; the readable conversation record is an editable local record, not independently verified evidence of successful tool execution. Requested argument excerpts are bounded and redact recognizable credential patterns, but redaction is not a guarantee for arbitrary secrets. Avoid speaking secrets you do not want in a local transcript.

## Verification and known limits

The default native audio model passed a real spoken-input → Knowledge lookup → audio-response probe through the local bridge, including signed start/end records. The extended-thinking Live option connected and spoke a filler sentence but did not emit its Knowledge call before timeout; retrieval with that option remains open, and it is not the default. The desktop acceptance suite uses synthetic microphone/provider traffic without recording the user's microphone. It checks voice-only persistence, resume/export, four-theme contrast and narrow layout.

Failed saves are shown in Voice Mode with **Retry saving**. Retry before closing the app. Entries not yet saved can be lost on a forced exit. Transcript accuracy depends on the selected speech service.
