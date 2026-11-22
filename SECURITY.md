# Security policy

Do not post credentials, private project files, phone sessions, conversation databases or exploitable security details in public issues. Use [private vulnerability reporting](https://github.com/Artyfowl1710/indra_Origo-Labs/security/advisories/new) for security reports.

The desktop backend binds to loopback by default. Phone dashboard sharing is optional and needs private networking and authentication. Messaging bots have their own allowlists; never make a workstation agent available to arbitrary senders. Treat documents, retrieved text, web pages and model output as untrusted input. A retrieved instruction is not user authorization.

Keep approval checks enabled. Grant narrow project folders and review commands/edits. Docker execution must not silently fall back to unrestricted host execution. A hash chain or signature can detect some later changes to records; it cannot prove that every action was correct, complete or externally witnessed. A compromised host can compromise its keys.

API providers receive the context you send them. Offline retrieval is local, but provider inference, speech and connectors can use networks. Credentials are stored in the local user profile; operating-system account access matters. Use provider quotas and rotate exposed keys. Never include a working .env in a bug report.

The public package is scanned before publishing. Scanning is defense in depth, not an independent security audit. The Windows candidate is unsigned and still needs broader independent installation testing. Dependency versions and license notices are included for review.
