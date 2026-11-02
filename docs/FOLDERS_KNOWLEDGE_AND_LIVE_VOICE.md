# Folder selection, agent retrieval and voice — 1 November 2026

## Select a project folder

In Chat → Projects, press **+**. The Windows folder picker opens in the native Indra app. Choose a folder, review the selected location, then press **Grant & index documents**. Cancel grants nothing. Pasting a path remains an alternative for remote/browser access. The native picker accepts requests only from the owning Indra window's main frame and origin. Existing folder-grant validation and tool approvals remain in effect.

## Knowledge is available to the agent

Typed and harness-voice chat turns receive retrieved passages from the selected collection. The model can also call the read-only **knowledge_search** tool during its work, list available collections, and search a granted project or personal library. The tool is supplied by the product's retrieval plugin and is available in normal file-enabled and coding toolsets. It cannot grant folders, browse other profiles, index arbitrary paths or execute document instructions. Revocation and per-profile/per-project indexes still apply. See WORKSPACE_UPGRADE.md for indexing and extraction limits.

## Two voice controls

- **Dictate** records a draft; press **Stop dictation** to transcribe into the composer. It does not automatically send that draft. Capture is bounded to 60 seconds/8 MiB per draft. Browser SpeechRecognition is no longer required. Google transcription is preferred when a Google key is connected, otherwise the configured speech provider is used. The account's model catalog is cached to avoid selecting retired transcription models.
- **Voice Mode** opens **Google Live voice** by default. Press Start Google Live to begin continuous native-audio conversation with thinking. Mute/unmute, stop playback, end call and close release or pause the relevant resources. Backgrounding the app mutes Live input; unmute explicitly to resume. Session resumption and context-window compression are enabled; the app imposes no fixed duration on a Live conversation. Google still controls quotas, availability, billing and session limits.
- **Use harness voice instead** retains conversation through the coding agent, device/backend speech and the existing approval flow. Google is preferred for transcription when connected. Computer actions requested in Live voice can be handed to the coding chat using **Send last request to coding agent** after ending the call. Live itself has read-only Knowledge search, not direct computer execution.

Google Live uses the Google credential already saved in Runtime. An OpenRouter key cannot authenticate Google's Live service. The permanent Google key stays on the backend; the renderer receives a short-lived, one-use token. Tokens are not persisted. Microphone access requires consent in the native app. Closing voice, changing profile or closing the app releases capture. A live connection may incur Google usage charges; an account displaying Unlimited for some rate dimensions is not an unconditional availability guarantee.

## Verification and provider limits

The native-audio model `gemini-2.5-flash-native-audio-preview-12-2025` passed a real synthetic spoken-audio test with dynamic thinking enabled: Google called Knowledge retrieval and returned spoken PCM audio containing the indexed service interval. This verified model is the default. The `gemini-3.8-live-extended-thinking` choice completed setup but timed out without an answer in the same account's probes; it remains selectable rather than being silently substituted. See `data/test-results/google-live-voice.json`.

The real dictation endpoint also passed with offline-generated speech. Initial testing detected Google's retirement of the old `gemini-2.5-flash` text endpoint; account-catalog selection replaced that hardcoded model. No personal audio or documents were used in these provider tests.

Eleven native renderer checks exercise the folder IPC bridge, folder grant/index, dictation into the composer, Live stream/Knowledge callbacks, mute/unmute, stop playback, end-call cleanup, harness controls, settings and exit. Device input and Google transport are synthetic in this renderer suite; separate provider probes use real Google service calls. Human microphone/speaker quality and a long-duration real connection rotation have not been independently verified. Automated lifecycle tests cover cancellation, cleanup and resumption handles.
