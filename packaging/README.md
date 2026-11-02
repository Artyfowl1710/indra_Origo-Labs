# Rebuild the Windows candidate

Build on Windows x64 with Python 3.13, Node 22 and Git. From a clean checkout, create a Python virtual environment, install the lockfile, run `npm ci` in `indra/SIH-26/hermes-agent`, and run `npm run build --workspace web` there. In `indra/SIH-26/hermes-agent/scripts/whatsapp-bridge`, run `npm ci --omit=dev` if including WhatsApp.

Then, from the repository root:

```powershell
.\.indra-python\Scripts\python.exe packaging/prepare_windows.py
.\.indra-python\Scripts\python.exe packaging/build_windows.py
```

Preparation downloads the official Python embedded runtime and NSIS archive with fixed SHA-256 checks, installs the resolved Python lockfile into a fresh target, and fetches MiniLM assets at the recorded revision with hash verification. It does not copy a working profile or developer virtual environment into the package.

The builder assembles the native payload under a short, marked temporary build directory to accommodate Windows path limits. Release assets are written to `release-assets/`, which Git ignores. Rebuilding an already used candidate directory requires removing only that marked build directory after verifying its location. The build never silently deletes a user installation or profile.

The final installer is per-user and unsigned. Code signing, independent second-PC acceptance and a clean operating-system matrix are additional release steps. See the handbook's release section for the actual tested scope of the published artifact.
