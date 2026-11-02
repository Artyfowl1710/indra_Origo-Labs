# Customized Indra UI foundation

The user's recordings show the customized INDRA web dashboard, not the generic upstream Hermes Electron chat surface. Its source is `indra/SIH-26/hermes-agent/web`. The full surrounding Indra customizations have now been imported into `indra/SIH-26`, including indra_tools, skills, skins, dashboard themes, scripts, and supporting files. The reference directory remains read-only.

The customized web workspace build passed. `origo-desktop/main.cjs` hosts it in a sandboxed Electron application window. `start_origo_product.ps1` launches this application and its own Python dashboard backend on an available loopback port. Backend readiness was confirmed in the log. This is the correct product UI base for further Origo work. The generic imported Electron shell and the earlier Tk prototype remain separate development artifacts.

Source: the working SIH-26-main folder. Both supplied recordings were sampled locally to identify the correct UI. Customization import hashes are in indra/INDRA_CUSTOMIZATIONS_MANIFEST.json. Credentials were excluded; a sanitized configuration reference is provided for adapting the product settings. Existing user history, vaults, generated reports, caches, models, and environments were not silently treated as application source.

Open work includes migrating settings to explicit Origo defaults, wiring model selection and document/voice dependencies, preserving approval boundaries, branding and visual updates, installer packaging, and independent tests of the customized UI with Ollama and Dots. A ready backend and successful UI build do not establish those outcomes.
