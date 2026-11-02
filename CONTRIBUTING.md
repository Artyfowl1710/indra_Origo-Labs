# Contributing to Indra

Read the current handbook's development and testing pages before changing the runtime. Keep the product identity Indra, by Origo Labs; retain original upstream licenses and compatibility identifiers. Explain inherited versus new work accurately.

Use a fresh local profile for tests. Never include API keys, phone sessions, signing material, personal documents or conversation databases in a pull request. Start with a minimal fictional reproduction. For vulnerabilities, follow SECURITY.md rather than posting exploitable details publicly.

Preserve loopback defaults, folder scopes, approval checks and Docker isolation. Do not add an unrestricted host-execution fallback. Treat documents and model output as untrusted data. Include focused regression coverage for changed API/security contracts and report what was actually tested.

Dependency updates need coordinated lockfile and runtime validation. A provider catalog entry is not a verified integration; optional services should fail clearly. New themes and controls should be checked across light, teal and ember appearances with accessible contrast.
