# Candidate validation

Full results and limitations: [release-validation.json](provenance/release-validation.json).

The public source ran 310 product tests under the bundled Python runtime with zero failures and three skips. Two skips require Windows symlink permissions; the third reflects the deliberate absence of weights in Git. The packaged offline retrieval test passed separately with HTTP calls forbidden. The developer environment ran the same 310 tests with two skips. A focused imported-backend suite passed 29 tests, and three desktop path-isolation tests passed.

The completed fictional checkout snapshot passed 12 tests and its independent verifier. Protected inputs retain exact bytes through the Git index. Public-source scanning found no unreviewed credential/runtime artifacts; explicit synthetic test-vector exceptions are documented by path and hash.

The final Windows candidate installed, started its native UI and owned backend under an isolated profile, returned HTTP 200 for status/sessions/model settings, and executed the bundled Python with local project imports. Uninstalling removed the owned installation while preserving a profile sentinel. The portable archive passed full CRC validation and required-file/state exclusions. Startup timings are observations from this PC, not a benchmark or cross-machine guarantee.

The handbook was built and visually reviewed locally. GitHub Actions/Pages have not run until publication. The installer is unsigned, a second physical PC test remains outstanding, and not every optional connector or framework test has been exercised. The final formal video now includes the creator's narration; the X trailer uses a distinct synthetic narrator. Both were decoded and checked at 1080p/30fps with 48 kHz stereo audio. No repository push, live website deployment or release publication has been performed by this preparation task.
