# Main publication receipt

[PR #2](https://github.com/groxaxo/mempalace/pull/2) was merged into
`groxaxo/mempalace:main` at **2026-11-11 12:07:24 UTC** under the user's explicit
instruction to commit, push, merge and document the corrected ingestion work.

| Record | Commit |
| --- | --- |
| Main bootstrap: v3.11.0 plus fork image-publication guard | `d5a5d7a704b0c2e40437bf6a003c12c6dfde6126` |
| Corrected implementation, regressions and review documentation | `174dcc4b4ca24ad8f6052cdbd3f6141b67a2ec8a` |
| Python 3.9 CI runner compatibility | `31acb110f7ed85d0f431c55ecfe5b9bd26f7e7ac` |
| PR merge into main | `1c305eb1712a10cd313d3e3e8b5be63c971d8394` |

The fork previously had no `main`. Its existing `develop` branch and default
branch remain unchanged. No force push, protection override, release tag,
package release, production deployment or real-data reingestion was performed.
The Docker publishing job is restricted to upstream releases or nonpublishing
PR validation; fork main pushes cannot publish release images.

## Verification

The merged Git tree exactly matched the PR head, and all **21** source/CI
fingerprints in `PUBLICATION_MANIFEST.json` matched the checked-out files.
The corrected source freeze SHA-256 is
`19502332eb23d6cda362573fb3714e77aadc467eceef4c5624a478c976fc7a0c`.

Local checks passed: **733 selected tests** (290 safeguards plus 443 affected
upstream cases), Ruff check/format, compilation, all 13 version values, and the
synthetic shadow demo. Captured commands/output are in
[review-third-fixes](review-third-fixes/README.md). R1–R5 and the additional
candidate-review cases are documented in
[THIRD_CORRECTION.md](THIRD_CORRECTION.md). The final receipt commit changes
only publication documentation; it does not alter the tested runtime source.

## GitHub CI snapshot

Observed at `2026-11-11T12:09:28.109109+00:00` for PR head `31acb110f7ed85d0f431c55ecfe5b9bd26f7e7ac`:

- [Version Guard](https://github.com/groxaxo/mempalace/actions/runs/43017420590): passed.
- [Tests](https://github.com/groxaxo/mempalace/actions/runs/43017420640): still running; lint passed, and all three Linux Python versions reached pytest.
- [Docker](https://github.com/groxaxo/mempalace/actions/runs/43017420592): still running; smoke and GPU validation passed, with the nonpublishing PR image build in progress.

The first attempt could not install Python 3.9 on Ubuntu 26.04 and cancelled
its sibling Linux entries. The corrected matrix pins only Python 3.9 to Ubuntu
24.04. No tests were removed to accommodate that setup failure. No full GitHub
CI pass is claimed by this snapshot; the linked runs show later status. The
branch had no required status checks, and the user-authorized merge did not
bypass protection or required reviews.

## Deployment remains blocked

Accepted replacement can still delete old records before a later write fails,
and some writers remain ungated. Establish replacement safety with failure
injection on disposable data before valuable reingestion; a backup is not
proof. Full local upstream validation, the separately requested Claude review,
real-model extraction and deployed transports remain outside the completed
local checks. Historical failed reviews retain their original disposition.
