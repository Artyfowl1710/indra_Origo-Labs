# Build status

Verified on 31 October 2026:

- Origo Remote 1.1.0, package `ai.indra.origo.remote`, version code 2.
- JDK 21 from Android Studio; Gradle 8.13 wrapper pinned to the official SHA-256; Android platform/target 35; minimum API 26.
- `testDebugUnitTest assembleDebug` passed. Three JVM endpoint-policy tests, zero failures or skips.
- Cached offline rebuild passed. Wrapper-based `scripts/build_android.ps1` passed and packaged the artifact.
- `apksigner verify --verbose` passed using APK Signature Scheme v2, one debug signer.
- Manifest permissions: Internet and microphone. Microphone hardware is optional.
- Artifact: `../../dist/OrigoRemote-1.1.0-debug.apk`, 827,021 bytes.
- SHA-256: `b99dffc92b6d17a75559151d62d84ba6e0c5a5a64a81bd8d3b4a828d5423fc2e`.

Not yet verified: physical-device/emulator installation, file-picker upload, microphone permission/capture, current-backend private HTTPS pairing, session revocation, cross-device handoff, clean-machine build and distribution signing. Compilation and pure endpoint tests do not establish these runtime behaviors.
