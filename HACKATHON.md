# Hackathon contribution boundary

Indra extends an existing project. Reviewers should evaluate the new workflow and engineering changes, rather than attributing the entire imported agent framework to the hackathon.

## Existing foundation

The parent repository is [Indra_lok](https://github.com/Artyfowl1710/Indra_lok), inspected at public commit `8136195edc37187f08974c196e0370cdcac83280`. The working SIH folder imported for this project can differ from that public snapshot. Its initial file hashes are preserved in [the import record](provenance/imported-source-hashes.json); this record does not reconstruct a missing Git history.

[File comparison against the import snapshot](provenance/changes-from-import.csv) records changed, unchanged and unlisted files. A file absent from that manifest is not automatically proven to have been written during the event; the comparison is an inspection aid, not a fabricated development history.

Inherited foundations include agent/tool orchestration, connectors, terminal/file tools, office document generation, initial retrieval/voice capabilities and distributed/local model support. The imported code also incorporates the Hermes framework from Nous Research under MIT. These are substantial existing capabilities.

## Work developed and refined for this submission

During the current build period, the work integrated a native Indra workbench with Origo Labs identity, local startup, a system folder picker and appearance fixes; a project/goal workflow with verifiable completion; offline compact embeddings and document evidence access; model catalogs, capability roles and modality routing; artifact discovery/preview repairs; audit/provenance presentation; voice controls; and branded Telegram/WhatsApp onboarding and phone approval flows. Packaging and the judge handbook make that workflow reviewable.

These are integration and refinement claims, not a claim to have invented retrieval, cryptographic signatures, agent tools or messaging adapters. See source, regression tests and the real screen recording. Dates in a file or this document are not substitutes for independently verifiable commit history.

## How this differs from the SIH parent

| Area | Existing SIH/framework foundation | Current Indra submission emphasis |
| --- | --- | --- |
| Entry point | Developer/client scripts and enterprise analyst workflows | Native desktop startup, portable runtime paths, branded workbench and folder selector |
| Work unit | Chat and tool execution | Scoped project plus a measurable goal and independent completion check |
| Documents | Existing RAG/document tooling | Compact offline embeddings, document evidence workflow and scoped agent retrieval integration |
| Deliverables | Existing office/file generation | Artifact discovery/preview repair, visible output evidence and a verifiable handoff |
| Models | Existing inference/client integrations | Capability-aware catalogs, auxiliary roles, API/local routing and clearer configuration |
| Phone | Existing adapter capabilities | Integrated onboarding, self-chat/owner setup, branded controls and demonstrated permission flow |
| Reviewability | Existing logging | Provenance verification presentation, attribution and explicit limits |
| Distribution | Existing development setup | Public handbook, curated evidence, bundled Windows candidate and release checks |

Reviewer starting points: [desktop lifecycle](origo-desktop/main.cjs), [native folder bridge](origo-desktop/workspace-native.cjs), [workspace services](origo_runtime/workspace.py), [offline encoder](origo_runtime/embeddings.py), [regression tests](tests/) and [recorded run](examples/recorded-run/README.md). The imported framework remains the foundation; these links describe integration work rather than an entirely new agent engine.

## Recorded model and task

The recorded desktop workflow is configured to `baseten` / `meta-models/muse-spark-open-1026`. It repairs a fictional checkout implementation using scoped requirements, produces tests and deliverables, and checks the goal. The published recorded-run snapshot contains 12 passing tests. The phone segment is a separate task and should not be described as the exact same desktop task continuing on another device.

The phone clip demonstrates a permission choice and returned files. Its dependency installation encountered an SSL failure, so successful execution of that phone-generated cryptography program is not claimed. Gallery UI captures are labelled separately from real recording evidence.

## Submission checklist

- Public source repository and accessible video link.
- Clearly distinguish the original foundation from event-period changes.
- List every actual contributor on the submission; maximum four participants.
- Use only assets and code for which the team has rights. Third-party notices remain included.
- Final upload must meet the organizer's current rules and deadline; this document does not publish a submission automatically.

Reference: [official participant guide](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/details). The supplied guide specifies a three-minute demo and a public repository.
