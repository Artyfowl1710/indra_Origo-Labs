# Origo Remote for Android

Android companion source for connecting to the user's own Indra Origo PC. It remembers the chosen HTTPS endpoint and reconnects on launch. It is a private web client, not a hosted relay and not a public internet tunnel.

## Current build

Origo Remote 1.1.0 (version code 2) has been compiled and debug-signed. The verified personal-test APK is at `../../dist/OrigoRemote-1.1.0-debug.apk`, with an adjacent SHA-256 file. It supports Android 8.0 and later and targets Android 15. APK signature verification and three endpoint-policy JVM tests passed. Physical-device and emulator acceptance remain open.

The companion includes a system document picker, same-origin microphone permission requests, accurate main-page network/HTTP/TLS error states, and a disconnect action that clears its saved endpoint, cookies and web storage. Microphone access is optional; it is requested when the trusted workstation page requests recording.

## Private connection model

- Install Tailscale on the PC and Android phone and sign both into the same private tailnet.
- On the PC, Origo remains bound to `127.0.0.1`; Tailscale Serve provides the private HTTPS endpoint.
- The current desktop's **Origo → Phone pairing…** window configures its own dashboard authentication and managed private sharing. See [current pairing instructions](../../docs/PHONE_PAIRING.md). The older `enable_remote_tailscale.ps1` targets the original FastAPI app and port 8765; it is **not** a pairing setup for the current automatic-routing desktop. Actual phone/Tailscale acceptance remains pending.
- Paste the `https://…ts.net` URL into the app once. It is stored in private app preferences and opened automatically on later launches.
- Sign-in and session expiry are controlled by the configured PC backend. The original app used token sign-in; the customized backend supports its dashboard authentication providers. This companion does not invent a second authentication scheme. Tailnet ACLs remain defense in depth: only trusted personal devices/users should be members. Do not port-forward Origo or expose it directly to the public internet.
- Disconnect clears this app's local session. It does not revoke a stateless PC session on other devices; server-side session revocation and current-backend pairing remain acceptance work.

The app accepts only root-level HTTPS `*.ts.net` endpoints, rejects cleartext HTTP and custom ports, disallows mixed content and local file access, keeps navigation on the configured HTTPS origin, and sends external HTTPS links to the system browser. The web UI requires JavaScript, so JavaScript is enabled only in the trusted configured origin. The access token is entered into the login page; it is not stored in Android preferences.

## Build the APK

From the Origo project root, with Android Studio's JDK (or JDK 17+) and Android SDK platform 35 installed:

```powershell
.\scripts\build_android.ps1
# After the pinned Gradle distribution and dependencies have been cached:
.\scripts\build_android.ps1 -Offline
```

The script runs tests, assembles the APK, verifies its signature and copies it plus a checksum to `dist/`. It accepts `-JavaHome` and `-AndroidSdk` overrides. The wrapper pins Gradle 8.13 and validates its official distribution checksum. Initial builds require dependency downloads; the offline rebuild was verified on the development PC. A fresh-machine install is not yet verified.

Alternatively, build in Android Studio:

1. Open this `OrigoRemote` folder in Android Studio and allow Gradle sync.
2. Select **Build → Build Bundle(s) / APK(s) → Build APK(s)**.
3. Debug APK output: `app/build/outputs/apk/debug/app-debug.apk`.
4. For personal testing, transfer the debug APK to your phone and install it using Android's normal package installer. Distribution signing, device tests and pairing integration remain open; never commit a release keystore.

Package ID: `ai.indra.origo.remote`; minimum Android 8.0 (API 26).
