---
name: Secure Local Plugin Development
description: Design and verify a minimal, least-privilege Indra Origo local JSON plugin.
---
# Secure Local Plugin Development

## Goal
Build a small integration through the declarative local HTTP JSON plugin contract. Keep the host harness independent of plugin implementation language.

## Workflow
1. Define the smallest read-only capability that solves the use case. Separate reads from mutations and do not disguise side effects as search or lookup.
2. Inspect `docs/EXTENSIONS_AND_WEB.md`, `plugins/README.md`, the example manifest, and the example service before designing a manifest.
3. Bind the service to a numeric loopback address only; do not use a public endpoint or expose it to the LAN. Add explicit route, method, body-size, response-size and timeout limits in the service.
4. Use a strict object schema with `additionalProperties: false`, bounded strings/numbers, a small required-field list and a meaningful description. Never accept arbitrary file paths, shell strings, raw SQL or unbounded URLs as model arguments.
5. Do not trust `read_only: true` as a security guarantee. Review the endpoint implementation and its data access to confirm it cannot mutate state.
6. Ensure logs omit secrets and sensitive request contents. Return bounded JSON errors that do not reveal stack traces or internal paths.
7. Keep the manifest disabled until manually reviewed. Enable both the manifest flag and the global environment gate deliberately.
8. Run `scripts/validate_extensions.py` and `python -m unittest discover -s tests -v`. Add tests for invalid input, timeouts, oversized responses, permissions, and failure behavior.
9. Report the files changed, capability boundary, data sent to the service, tests actually run and remaining risks.

## Output
Manifest/schema, service implementation plan, tests, local-only run instructions, rollback/disable steps, and a short threat-model note. Never claim the integration is sandboxed merely because the manifest is declarative.
