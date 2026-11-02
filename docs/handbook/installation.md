# Install and first launch


## Windows x64 candidate

Offline knowledge retrieval uses ONNX Runtime, which requires Microsoft's Visual C++ v14 x64 runtime on Windows. If it is not already installed, use [Microsoft's supported x64 Redistributable](https://aka.ms/vc14/vc_redist.x64.exe) before testing offline knowledge. The Microsoft runtime is an operating-system prerequisite, not bundled by this project. See [Microsoft's documentation](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) and [ONNX Runtime requirements](https://onnxruntime.ai/docs/install/). The app bundles its own Python and Node runtimes.

Download the installer or portable ZIP from [Releases](https://github.com/Artyfowl1710/indra_Origo-Labs/releases). Verify the published SHA-256. Install for your user account and launch Indra. Python, Node and the desktop shell are bundled; the app starts and owns its loopback backend. Opening an `index.html` file is not a supported way to start it.

The installer does not contain a provider key, a configured messaging account or large local inference weights. First launch needs you to choose a provider. Network access is required for hosted inference. Local inference works after you separately install/configure a compatible server and weights.

The bundled handbook is available from the Start menu as **Indra Guide**. A copy of the fictional sample lives under the installation's `resources/app/examples/atlas-checkout` directory. Copy it into a new writable project folder before asking the agent to edit it; keep the installation itself intact.

## Your data

Installed/portable builds keep state at `%LOCALAPPDATA%\OrigoLabs\Indra`: `profile` holds settings, accounts and conversations; `desktop` holds desktop cache; `logs` contains startup diagnostics. An uninstall preserves this profile. Back it up securely if needed; it contains secrets. Do not upload it to GitHub.

## First-run checklist

Open Keys, save a credential, then Models and choose the provider/model. Start a new chat after model changes. Select a narrow writable project directory. Ask a small question first, then try the guided example. Do not enable phone sharing until local operation works.

The candidate is Windows-first. Linux/macOS source work is not an installer promise. A separate physical Windows PC test remains required; see [release validation](release.md).
