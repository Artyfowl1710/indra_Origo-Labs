# Indra source foundation

The active source foundation is `indra/SIH-26/hermes-agent`, imported from the user's working `SIH-26-main` folder. The reference folder remains untouched. `indra/IMPORT_MANIFEST.json` records source hashes and excluded credential-pattern candidates. The upstream LICENSE and author metadata are retained.

The import contains the Electron desktop, shared UI, backend, agent, tools, providers, skills, and tests. Existing Origo `app/` and `desktop.py` are retained as prior prototypes while integration proceeds. The copied root launch scripts are reference material and have not been run; their shared-port process cleanup is unsuitable for Origo's lifecycle.

Node dependencies are installed in the copied project. Its manifest/lock mismatch required dependency resolution in the copy. Lifecycle scripts were disabled during installation. The Electron build and Python 3.13 core installation are the next validation gates; a successful copy is not a completed desktop release.

Runtime settings and credentials must be configured separately for Origo. Do not copy the reference `.env`, user configuration, model weights, vault, databases, sessions, or environments into release packages.

Validation completed: copied desktop Electron/React build passed; the isolated Python 3.13 core imports successfully (Pydantic 2.13.4, FastAPI 0.162.0). start_origo_indra.ps1 selects the local copied core and Python runtime and separates Electron user data and HERMES_HOME beneath Origo/data. The launcher was executed. Desktop onboarding, model configuration, tool execution, release branding, and offline installer acceptance testing remain open. The existing source-stamp fallback warning also needs release packaging work.
