# Releases and GitHub Pages


The public source snapshot is separate from the working installation. Generated installer/portable binaries, checksums and the main demo video are uploaded as GitHub Release assets, not committed to Git. Source, tests, reviewed example outputs, screenshots and handbook content remain browsable in the repository.

The Windows candidate bundles a fresh Python runtime and packages, the native desktop runtime, Node for the WhatsApp bridge, compiled workbench assets and compact local embedding assets where licensed. It does not bundle API credentials, personal profiles or large inference models. Original third-party licenses are included.

GitHub Pages is generated from the handbook with the repository's documentation workflow. The publisher must enable Pages with the GitHub Actions source. The website is a user guide; it is not a hosted instance of the agent and cannot access the user's PC. Documentation builds have no access to private local profiles.

Release candidate status remains until an independent machine installation, first launch, provider connection and example task have been verified. Installer hashes detect changed downloads; they are not a code-signing certificate or proof of trust. Do not publish an unsigned candidate as universally tested production software.
