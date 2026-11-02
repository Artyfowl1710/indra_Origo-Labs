# Troubleshooting


| Symptom | Check |
| --- | --- |
| Unstyled page or buttons do nothing | Start the native app, not a file:// HTML page. |
| Startup waits or closes | Read LocalAppData/OrigoLabs/Indra/logs; check quarantined/missing files without disabling antivirus. |
| Inference unavailable | Select a configured provider/model; verify endpoint, key, access and local server state. A random loopback port from another PC is not portable. |
| Model missing | Refresh the provider catalog; confirm the account has access. Manual IDs must match the provider exactly. |
| Image tool unavailable | Configure a compatible vision model/endpoint or local projection; text-only inference is insufficient. |
| Knowledge empty | Check ingestion completion, scope, assets and supported file extraction. |
| Artifact 404 | Confirm the file really exists, has a unique name in allowed output roots and was created successfully. |
| Phone bot silent | Enable its channel, start/restart gateway, check allowlist, token and duplicate polling processes. |
| Voice silent | Check microphone permission, device, transcription provider, output voice and quota. |
| Package install SSL error | Check system clock, trust chain and current dependencies; do not bypass TLS verification. |

Before filing an issue, reproduce with a non-sensitive sample. Include version, OS, provider/model ID, steps and a redacted error. Do not upload `.env`, signing material, WhatsApp sessions or conversation databases. Profile backups may contain secrets even if a single screenshot does not.
