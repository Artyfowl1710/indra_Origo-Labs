# Roadmap

Indra's current release is a Windows x64 candidate. These are the priorities for the next release. Work is tracked through repository issues and pull requests. Release dates depend on validation and maintainer availability.

## Installation and first use

- Test the published installer on a clean Windows PC and document missing prerequisites.
- Make setup errors for local models and optional tools actionable.
- Prepare code signing for Windows releases.

## Local model serving

- Exercise the existing OpenAI-compatible connection against current llama.cpp and vLLM releases.
- Publish reproducible latency, throughput and memory measurements with model and hardware details.
- Expand signed-model verification coverage using real model bundles and deployment tests.

The signed-model launcher currently verifies a release before startup. Request-level receipts and hardware attestation are further work.

## Contribution and maintenance

- Keep installation, provider and troubleshooting documentation aligned with the release.
- Add regression coverage for reported failures, including concurrency and permission boundaries.
- Make it easier to reproduce a bug using fictional files and a fresh profile.

See [CONTRIBUTING.md](CONTRIBUTING.md) for reporting a problem or proposing a change. Funding proposals will identify a smaller set of deliverables and a budget for that work.
