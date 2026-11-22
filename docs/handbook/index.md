# Indra handbook

<figure class="city-hero">
<video id="city-hero-video" autoplay muted loop playsinline preload="metadata" poster="../media/city-poster.webp" aria-hidden="true" src="../media/indra-city.mp4"></video>
<div class="hero-copy"><h2>Work on a project<br>with your own models.</h2><p>Choose a model, grant access to a project folder, and review proposed changes.</p></div>
<button id="hero-motion" type="button">Pause scene</button>
</figure>

[Download the Windows candidate](https://github.com/Artyfowl1710/indra_Origo-Labs/releases/tag/v1.8.0-rc.1) · [Source code](https://github.com/Artyfowl1710/indra_Origo-Labs) · [Contribute](../../CONTRIBUTING.md)


Indra is an open-source agent workstation from Origo Labs. It brings project files, document retrieval, model connections, approval decisions and test results into one desktop application. Start with [installation](installation.md), connect a [model provider](providers.md), then select a [project and goal](projects.md).

The desktop and document index run locally. You can connect a hosted provider or a separately installed local model server. Hosted providers receive the context sent in requests. The current release is a Windows x64 candidate, with [installation and integration limits](limitations.md) still being tested.

## Try the example project

1. Install the native desktop package and open Indra.
2. Add your own provider key or local endpoint.
3. Copy the example project into a writable folder and select it through Projects.
4. Ask the agent to inspect requirements, propose a plan and establish the failing test baseline.
5. Review the proposed work, inspect generated artifacts and run the example verifier.

The [recorded demo walkthrough](judges.md) gives the exact checkout task and prompt. It uses fictional files and includes a completed snapshot for comparison. The [demo recording](https://github.com/Artyfowl1710/indra_Origo-Labs/releases/download/v1.8.0-rc.1/Indra-real-footage-3min.mp4) uses actual product footage with synthetic narration. [Test evidence](evidence.md) records which workflows have been exercised.

## Build and contribute

Use the [source development guide](development.md) to set up the desktop and the [testing guide](testing.md) to run checks. The [contribution guide](../../CONTRIBUTING.md) covers bug reports and pull requests. The [roadmap](../../ROADMAP.md) lists the current development priorities.

Indra's integration code is MIT-licensed. The imported agent foundation and other components retain their original licenses and authorship. See [LICENSE](../../LICENSE) and [NOTICE](../../NOTICE.md).
