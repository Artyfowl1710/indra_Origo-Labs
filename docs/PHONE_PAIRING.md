# Phone pairing for the current desktop

The native desktop now includes **Origo → Phone pairing…**. This setup belongs to the customized automatic-routing desktop; it replaces the old app's port-8765 pairing instructions for this surface.

1. Use Tailscale on the PC and phone with your own private network. Tailscale sign-in and HTTPS authorization are performed by you in Tailscale.
2. In Phone pairing, enter this PC's root `https://…ts.net` address, a workstation username and a password of at least 12 characters. The default local port is 8766.
3. Select **Save and restart Origo**. The PC dashboard now requires sign-in as well. Passwords are scrypt-hashed; credentials stay in the local profile. Saving changes rotates the signing secret, invalidating older sessions after restart.
4. The setup status reports whether private sharing is active or needs Tailscale setup. When active, open Origo Remote 1.1.0 on the phone, paste the same address and sign in.
5. **Stop phone sharing and restart** stops the managed sharing session while keeping workstation sign-in protection enabled. It rotates existing session credentials as well.

The supervisor uses foreground Tailscale Serve, without Funnel or persistent `--bg` routes. It checks the signed vendor binary, exact node DNS name, configured local port, dashboard ownership and unauthenticated API rejection before publishing. An existing Serve configuration is left untouched. The foreground process is stopped when its desktop or backend owner exits; it never issues a global reset. Tailscale documents foreground sessions as lifetime-bound, including ungraceful client shutdown, in its [Serve configuration implementation](https://github.com/tailscale/tailscale/blob/main/ipn/serve.go) and [Serve documentation](https://tailscale.com/docs/reference/examples/serve).

The native setup is a sandboxed, isolated renderer. Only its exact main frame can invoke settings IPC. The remotely served dashboard does not receive a native configuration bridge.

The sharing supervisor also requires a strict Windows job and explicitly assigns its CLI child's creation handle, so supervisor crashes do not rely solely on Python cleanup. Startup refuses a missing containment guarantee. This process policy is tested with controlled sharing fixtures and real native process trees; actual Tailscale/device acceptance remains pending. See RUNTIME_PROCESS_OWNERSHIP.md.

## Verification and limits

- Nine phone-settings tests passed: address/field bounds, hashing, rotation, missing credentials, malformed/oversized settings, permission failure and local-profile preservation.
- Six route/lifecycle tests passed with controlled service/process fixtures, including refusal of an ungated backend or existing sharing configuration and cleanup on owner loss/cancellation.
- Five Node IPC-policy tests and three real Electron renderer checks passed. Dark and light setup renders were visually inspected.
- A real isolated dashboard passed nine live checks: loopback/public-host auth rejection, wrong-password rejection, successful sign-in, authenticated session, one-use WebSocket ticket, and session revocation/re-login after signing-key rotation.
- Actual Tailscale publication, phone TLS, APK installation, attachment/microphone behavior and cross-device continuation are still unverified. The user deferred live phone testing on 31 October 2026. No sharing was enabled and no active-profile authentication settings were changed during this implementation.

The APK remains at `dist/OrigoRemote-1.1.0-debug.apk`. The old `enable_remote_tailscale.ps1` continues to target the original FastAPI app; do not use it to publish this desktop backend.
