# Windows installation and first-run guide

## Supported baseline

- Windows 10/11, 64-bit.
- Python 3.10 or newer and the Python Launcher (`py`) recommended.
- PowerShell available.
- Internet access for the first dependency installation.
- A writable folder outside protected Windows directories, e.g. `C:\AI\indra-origo`.
- Optional: Node.js for JavaScript syntax validation; Docker Desktop for the isolated command sandbox; Tailscale for remote access.

## Install

1. Download the release ZIP from the project's private GitHub Releases page (or use the source ZIP supplied by the maintainer).
2. Extract it to `C:\AI\indra-origo`. Do not run it from inside the ZIP or from a read-only/protected folder.
3. Open the extracted folder. Inspect `.env.example`, `docs/SECURITY_MODEL.md`, and `REMOTE_ACCESS.md` before enabling optional network features.
4. Double-click `start_origo.bat`. On first launch the setup script creates `.env`, a Python virtual environment, `workspace`, `data`, backups and logs; installs the exact pins in `requirements.txt`; compiles Python; runs `unittest`; validates skills/plugins; and checks JS syntax if Node is installed.
5. Wait for the terminal to report startup success. Open the URL printed by the launcher, normally `http://127.0.0.1:8765`.
6. Open **Diagnostics** in the UI. A healthy web app does not imply a model is available; model service setup is separate.

## First-run checklist

- [ ] The browser URL uses `127.0.0.1`, not a LAN IP or `0.0.0.0`.
- [ ] `/api/health` returns `ok: true` in the local browser.
- [ ] Diagnostics reports the expected provider/model endpoint.
- [ ] A small prompt succeeds only after a model endpoint is configured and reachable.
- [ ] Create a test file in the Origo workspace and confirm it is visible in Files & context.
- [ ] Try a proposed edit on a disposable file; confirm it requires approval and creates a backup.
- [ ] Confirm `.env`, `data/`, `logs/`, and `.venv/` are not tracked by Git.
- [ ] Keep remote access and Docker sandbox disabled until you intentionally configure them.

## Stop and restart

- Stop: run `stop_windows.ps1` from the extracted project folder.
- Restart: close the previous server cleanly, then run `start_origo.bat` again.
- If the default port is occupied, the launcher tries ports 8765–8775 and reports the selected port. Use the actual port in diagnostics and remote setup.

## Model gateway setup

The default is an OpenAI-compatible endpoint through llama-swap:

```env
OPENAI_BASE_URL=http://127.0.0.1:8100/v1
OPENAI_API_KEY=local
MODEL=auto
LLAMA_SWAP_URL=http://127.0.0.1:8100
LLAMA_SERVER_URL=http://127.0.0.1:5800
```

Start your model server/gateway separately. Origo does not download or launch model weights. Check `http://127.0.0.1:8100/v1/models` in a local browser or use Diagnostics. Use a model alias actually advertised by your gateway if `auto` does not select the expected model. Hosted providers may receive prompts and retrieved context; read their data terms before configuring one.

## Docker sandbox (optional)

1. Install and start Docker Desktop with Linux containers.
2. Review `docker/Dockerfile.dev-sandbox` and `docs/SECURITY_MODEL.md`.
3. Enable **Permissions → Docker sandbox** inside Origo.
4. Build the development image or pull the configured sandbox image after reviewing the confirmation.
5. Run `python --version` first. Networking is disabled by default. A separately approved networked run has broad outbound reachability, not per-domain filtering.

## Remote access (optional and higher risk)

Follow [REMOTE_ACCESS.md](../REMOTE_ACCESS.md) only after local mode works. Remote access requires Tailscale on both devices, Tailscale Serve, a generated Origo token and an explicit `.env` opt-in. Never port-forward the app or bind it to `0.0.0.0`. The PC must stay awake and connected. This is a single-user personal workstation, not a multi-user service.

## Clean uninstall

1. Stop Origo and disable remote access if enabled.
2. Confirm `tailscale serve status` has no Origo route; the disable script may reset Serve configuration, so inspect other routes first.
3. Remove the extracted project folder. This also removes local app data, conversations, indexed knowledge and backups stored inside it. Export anything you need first.
4. Remove the Python virtual environment if it lives elsewhere. Docker images are independent; remove only images you intentionally created and no longer need.
