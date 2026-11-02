# Voice and Android verification increment

The Android companion now builds as version 1.1.0 and has a verified personal-test debug APK in `dist/`. See `android/OrigoRemote/README.md` and `BUILD_STATUS.md` for build evidence and the remaining pairing/device work. The original remote-access script addresses the old backend; it must not be presented as current-desktop pairing.

The customized desktop conversation mode had three important gaps: it advertised unconditional offline speech while selecting from all browser voices, pending transcription could submit after closing the modal, and pending microphone permission or backend speech could resume recording/playback after cancellation. Changes now restrict device speech to voices with `localService=true`, report unavailable device speech, forward abort signals through the existing authenticated transcription/speech API, and invalidate stale request results. Hidden/background voice mode mutes recording, stops playback and cancels pending transcription; resuming requires unmuting. Recording is bounded to approximately one minute per utterance.

The UI names configured speech providers instead of claiming that every model/transcription/speech path is offline. These changes make provider choice visible; fully offline voice still requires installed local speech models/voices and live audio acceptance.

The Android picker implementation follows the documented [WebChromeClient callback contract](https://developer.android.com/reference/android/webkit/WebChromeClient). The companion keeps file/content URL access disabled; actual selected-document upload must be checked on a device, rather than inferred from compilation.

Verification: 19 focused Vitest tests passed across voice selection, request ownership, authenticated API forwarding and palette checks; TypeScript/Vite production build passed. These tests cover request cancellation and stale-result policy, not physical audio hardware or the full rendered conversation component. APK build/signature/policy evidence is recorded separately in BUILD_STATUS.md.

Open acceptance: real microphone and speaker tests, barge-in during provider loading/playback, Android permission denial/cancellation, background transitions, local STT dependency/model readiness, current desktop remote-auth pairing and cross-device continuation.
