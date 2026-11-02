# Local Live voice bridge

Indra's native voice client now connects to the authenticated local backend rather than opening a provider WebSocket. The existing generic model selector, microphone, mute, playback, Knowledge search, resumption and conversation records remain available. Provider credentials stay on the backend; the renderer receives only its normal local session authentication and an opaque voice-session ID.

## Request and security flow

`/api/indra/voice/live` accepts the dashboard's existing session token or, in gated mode, a fresh single-use WebSocket ticket. Host, Origin and peer checks run before admission. The selected profile supplies its own key and content policy. The provider endpoint is fixed in the adapter; a query parameter cannot redirect it. Upstream authentication uses a header, with transport debug logging suppressed so a global debug setting cannot print its credential.

The first frame must bind setup to the selected model. Later frames must be JSON `realtimeInput`, `clientContent` or `toolResponse` messages. Duplicate keys, nonfinite numbers, malformed/oversized messages and unexpected setup changes are refused. Every outgoing frame passes the registered-canary policy before forwarding. A short in-memory text window also catches a marker divided into adjacent text frames; opaque media is not retained in that window. This does not interpret spoken words or image pixels.

Canary/policy refusal closes the session and releases capture. It does not silently retry or select another model. When the content guard is enabled, the older `/token` endpoint refuses direct-provider credentials, closing that bypass. Compatibility profiles that explicitly leave the guard disabled retain the legacy endpoint.

The bridge bounds frame size, upstream queues, concurrent sessions, setup wait, reconnect attempts and session lifetime. One connection owns one upstream socket. Client disconnect, refusal, provider failure, cancellation and timed rotation close the upstream and release its slot. Resumption handles remain provider-owned; the client includes the latest handle on reconnect. Local admission limits do not establish or override provider quota.

Signed `voice.live_started` / `voice.live_ended` records identify the model/provider, session, outcome and sent frame/byte counts. They contain no audio or transcript. The renderer includes the opaque session ID in its readable conversation activity. These local transcripts are editable notes; signed events are separate provenance. Independent verification still requires exported audit checkpoints, as described in the security model.

The implementation follows the [Live WebSocket protocol](https://ai.google.dev/api/live) and [server-side SDK authentication](https://github.com/googleapis/python-genai/blob/main/google/genai/live.py). Model-specific tool behavior follows the [capabilities guide](https://ai.google.dev/gemini-api/docs/live-api/capabilities) and [extended-thinking model guide](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live-extended-thinking): 3.1 uses sequential tools; extended thinking requires non-blocking declarations and omits response scheduling. An utterance ending while background reasoning continues keeps the UI in its thinking state.

## Voice dialog

The dialog has a compact two-column desktop layout, a single-column narrow layout, a state indicator, generic model selection, explicit capture/record controls and first-use export guidance. Light, dark, blue and ember share semantic surfaces and controls. Decoration indicates connection state, not a measured audio level. Reduced-motion preferences disable its breathing animation.

## Verification

- 27 focused bridge tests use real loopback WebSocket receivers and the real ASGI route: forwarding, encoded/fragmented canary checks through shared policy, admission boundaries, profile/key isolation, signed incidents, corruption refusal, cancellation cleanup, resumption payloads, rotation and resource limits. Shared HTTP voice and canary regressions bring the focused run to 45 tests.
- 30 frontend tests include local URL construction, policy-stop cleanup, resumption, background status, model-specific scheduling and record/activity behavior. Production TypeScript/Vite build passed.
- 28 isolated native checks cover folder selection, voice controls, local bridge use, records/resume/export, text contrast and viewport fit in four themes, plus narrow layout. Device/provider streams are synthetic in this fixture; no real microphone was opened.
- A real `gemini-2.5-flash-native-audio-preview-12-2025` run through the bridge accepted synthetic speech, called offline Knowledge, returned “The service interval is six months” as spoken audio and produced valid signed start/end records. The real provider and audio generation were not mocked.
- Product regression: 275 tests, two skips; required compile, extension and JavaScript checks passed.

Local evidence is excluded from release archives: `data/test-results/live-bridge-core-tests.log`, `live-bridge-ui-tests.log`, `live-bridge-ui-build.log`, `voice-folder-native-acceptance.json`, `live-bridge-provider-acceptance.json` and `live-bridge-root-tests.log`. Theme screenshots are `indra-voice-{default,midnight,nous-blue,ember}.png` in that directory. Reproduce the native fixture with `scripts/verify_voice_desktop.ps1`; real synthetic provider acceptance uses `scripts/test_live_bridge_provider.py`. The older `test_google_live_voice.py` command delegates to the bridge verifier.

## Open acceptance

The extended-thinking 3.8 probe connected and spoke a filler sentence, but emitted no Knowledge tool call before timeout. Its native-tool retrieval acceptance remains open; the verified native-audio thinking model remains the default. A retrieval-assistance workaround needs implementation and real-provider verification. Human microphone/speaker quality, long-duration rotation and unsupported account models remain unverified. Baseten audio remains the separately documented turn-based adapter, not native duplex audio.

Other direct SDK/HTTP integrations, TTS paths, configured webhooks/telemetry and arbitrary program egress still need mandatory canary mediation. The bridge does not provide semantic media inspection, a trained classifier or OS-wide DLP. The rest of the [full acceptance ledger](PRODUCT_GOAL_ACCEPTANCE.md) remains in scope.
