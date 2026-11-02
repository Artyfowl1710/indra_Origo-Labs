# Source development


## Requirements

For Windows source development use Python 3.13 x64, a supported current Node installation and Git. The bundled release avoids these developer prerequisites. Use a new virtual environment; do not install into the author's existing environment or point at their profile.

From the repository root:

```powershell
py -3.13 -m venv .indra-python
.\.indra-python\Scripts\python.exe -m pip install -r requirements-release.txt
$env:PYTHONPATH = "$PWD\indra\SIH-26;$PWD\indra\SIH-26\hermes-agent;$PWD"
Push-Location .\indra\SIH-26\hermes-agent
npm ci
npm run build --workspace web
Pop-Location
& .\indra\SIH-26\hermes-agent\node_modules\electron\dist\electron.exe .\origo-desktop
```

The workspace lockfile governs npm installation; if Electron is hoisted elsewhere, use its installed workspace path. Do not run unreviewed install hooks as administrator. The build output must be at `hermes_cli/web_dist/index.html`. Internal module names are necessary for imports. The root `app/` package also contains the earlier standalone API/prototype; it is not the native desktop entry point.

Source defaults keep a developer profile under `data/indra-product-home`. The packaged release uses LocalAppData instead. `ORIGO_HOME`, `ORIGO_PYTHON`, `ORIGO_DESKTOP_USER_DATA` and `ORIGO_LOG_DIR` provide explicit test/development overrides. Never set them to somebody else's profile for a public demo.

## Extending tools and providers

Preserve approval-first execution, loopback defaults and immutable session/caching assumptions. Add focused tests for new API contracts and security boundaries. Keep optional dependencies optional and report failures. Use [testing](testing.md) before shipping. Upstream documentation inside the imported framework is reference material; product instructions live in this handbook.
