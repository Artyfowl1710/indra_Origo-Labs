# Indra 1.8.0-rc.1 · Windows x64 candidate

Native Indra desktop application by Origo Labs, with a bundled Python/Node/desktop runtime and an offline compact embedding model. Add your own hosted-provider key or separately configured local model endpoint. Large inference weights, personal profiles and paired phone accounts are excluded.

The repository includes a 17-page user/developer handbook, a GitHub Pages workflow, curated UI screenshots, real recorded clips, the intentionally buggy checkout starter and a separate completed Meta-model run with generated reports and tests. Read HACKATHON.md for the boundary between inherited SIH/framework capabilities and this submission's work.

Download the installer for a per-user installation, or the portable ZIP. Compare your download's SHA-256 with SHA256SUMS.txt. The candidate is unsigned; no antivirus exclusions or TLS bypasses are supplied. The desktop owns its loopback backend and stores user state outside the installation directory. Uninstalling preserves the profile.

Read `INSTALL-FIRST.txt`. Offline retrieval's ONNX dependency needs the Microsoft Visual C++ v14 x64 Redistributable if your Windows PC does not already have it. The installation guide links directly to Microsoft's installer; the Microsoft runtime is not redistributed in this package. Python and Node are bundled.

Validation scope and results are recorded in provenance/release-validation.json. Independent acceptance on a second physical Windows PC is still required. This is deliberately published as a prerelease, not a claim that every machine, optional connector or provider has been tested.

The three-minute real-footage cut now includes the creator's English narration, in recording-time order, and a five-second city-animation opening. A separate 75-second X trailer uses a synthetic narrator and original synthesized music. The phone segment is a separate task; it does not establish successful execution of that task's generated program.

Original upstream license notices and dependency versions are retained.
