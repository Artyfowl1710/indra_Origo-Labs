# Local plugin manifests

Indra Origo supports **declarative local HTTP JSON plugins**. It does not import third-party Python/JavaScript into the host process. The manifest describes tools exposed by an explicitly enabled numeric-loopback HTTP service.

## Enable explicitly

1. Inspect the full example at `examples/local-notes/plugin.json` and its server at `examples/local-notes/server_stub.py`.
2. Start the example server from the project root in a separate PowerShell window:
   ```powershell
   .\.venv\Scripts\python.exe plugins\examples\local-notes\server_stub.py
   ```
   It binds only to `127.0.0.1:9911`, stores sample notes in memory, and does not read workspace files.
3. In the example `plugin.json`, change `"enabled": false` to `"enabled": true` after reviewing the manifest and server implementation.
4. Set `INDRA_ENABLE_LOCAL_HTTP_PLUGINS=true` in `.env`.
5. Restart Indra or click **Refresh registry** in Extensions. Confirm that the plugin is enabled in the UI or `GET /api/extensions`.

The `base_url` must use a numeric HTTP loopback IP (`127.0.0.1` or `::1`) with an explicit port; hostname aliases and remote endpoints are rejected. Every exposed tool must declare `"read_only": true`, use POST and a bounded object schema with `additionalProperties: false`. This is a **trust assertion**, not proof: POST can have side effects and the harness cannot infer the semantics of an endpoint. Only connect services you trust. Mutating tool support is not exposed to the model in this release; add a separate human-approval policy before supporting writes.

Responses are capped at 16 KB and plugin calls time out quickly. The example server is a reference contract, not a sandbox for other services. The plugin service process runs with its own permissions outside Indra's control. Never expose it to a LAN, store credentials in manifests or allow a plugin to bypass authorization.
