# Origo Remote: access your PC away from home

## Design

The Android companion stores a user's private HTTPS endpoint and automatically reconnects when opened. It does not rely on a shared public relay. Tailscale provides the encrypted private network; Tailscale Serve maps its HTTPS hostname to the existing loopback-only Origo service.

## Setup

1. Install Tailscale on the Windows PC and Android phone. Sign both into the same private tailnet. Use restrictive ACLs and enable MFA on the identity provider.
2. Start Origo normally and confirm the port. Default is 8765; the launcher may choose another port if it is occupied.
3. In an elevated or ordinary PowerShell window, from this extracted folder run `./enable_remote_tailscale.ps1 -Port 8765` (replace the port if needed).
4. The script sets `INDRA_REMOTE_ACCESS_ENABLED=true` in `.env`. Restart Origo so the explicit opt-in is loaded. Rerun the script and type `YES` only after checking tailnet membership/ACLs.
5. Copy the HTTPS `…ts.net` hostname printed by `tailscale serve status`.
6. Build/install the Android app from `android/OrigoRemote`, paste the HTTPS hostname once, and connect. The app remembers it and tries it on each launch.
7. The PC must remain powered on, awake, connected to the internet, and running Origo + Tailscale. Configure Windows sleep/power settings accordingly; this does not wake a sleeping PC.

## Security boundary and limitations

The backend remains a single-user workstation and is not suitable for shared multi-user tenancy. Remote `.ts.net` requests require a separate high-entropy `INDRA_REMOTE_ACCESS_TOKEN`; successful sign-in issues a host-bound, HMAC-signed 12-hour `Secure`, `HttpOnly`, `SameSite=Strict` cookie. Missing/short token configuration fails closed. Rotating the token invalidates prior cookies. The existing same-origin/Host guard remains defense in depth. Keep the tailnet restricted to your own trusted devices/users, use MFA on the Tailscale identity provider, and never expose the port-forwarded or public endpoint. This app-level token is not a replacement for tailnet ACLs or a production multi-user identity system.

The Android app is a WebView companion, not a native offline AI engine. Model inference still happens on the PC/configured provider. A dead PC, lost network, expired Tailscale login or unavailable model means the corresponding functionality is unavailable. The app stores the endpoint only, not passwords or API keys.

Disable remote access with `./enable_remote_tailscale.ps1 -Disable`, then restart Origo. The disable option resets Tailscale Serve configuration on this machine, so review whether you have other Serve routes before using it. To revoke sessions while keeping remote enabled, rotate `INDRA_REMOTE_ACCESS_TOKEN` in `.env` and restart Origo. Also verify `tailscale serve status` after any disable operation.
