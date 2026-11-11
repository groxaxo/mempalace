# Third correction and main integration

The user requested fixes for R1–R5 in `THIRD_REVIEW.json`, then explicitly
authorized committing, pushing, merging into the fork's `main`, and documenting
the result. The implementation remains experimental; merging source does not
approve production reingestion or resolve the existing deployment blockers.

## Corrected behavior

| Finding | Correction | Regression coverage |
| --- | --- | --- |
| R1: parser allocation | Enforce 16,384 lexical tokens and depth 32 before container parsing. AST parsing receives only a separately budgeted transformed candidate; never the original source. | Flat Python/JavaScript/JSON/encoded containers under a 128 MiB address-space cap; floor-division/comment ambiguity; pre-AST refusal. |
| R2: truncated envelopes | Use the same depth-aware family predicates for complete and truncated root structures, through late fields. Retain repeated-field evidence without copying whole trees. | Messages, ChatGPT, Slack, Claude, Gemini, Pi, wrappers, escaped/late/repeated fields, normalizers, and writer refusal before mutation. |
| R3: lexical false refusals | Recognize root structure before line-oriented parsers. Comments, strings, and unrelated nested configuration cannot supply envelope fields. | Python comments/triple strings and JavaScript comments containing both isolated records and complete conversation lines. |
| R4: JavaScript preservation | Recognize Unicode identifiers/escapes, template strings and nested interpolations, including regex atoms. Probe placeholders without evaluating expressions. | Admission, normalizers, formatting, writer preservation, combining marks, Other_ID_Start, escaped delimiters, interpolation and regex/division controls. |
| R5: Markdown fences | Track opening character and run length; require a matching sufficient-length closing run with a valid tail. | Nested shorter runs, mixed delimiters, invalid closer tails, longer valid closers, admission and writer preservation. |

Supported Slack `username` and Claude `sender` aliases remain normalized. Literal
omission-marker examples remain content, while generated omission provenance
stays separate from selected indexing text. Valid ordinary configuration and
source controls remain covered by the earlier suites.

`test_review_third_fixes.py` adds 61 cases. The guarded subprocess probes in the
second and third review suites run on Linux; other platforms still run the
portable controls. CPU/address-space/alarm/parent timeouts remain finite.

## Verification and freeze

Current captured output is in [review-third-fixes](review-third-fixes/README.md).
The final selected integration passed **733 tests**: 290 safeguards plus 443
affected upstream cases. Whole-checkout Ruff check/format, compilation, version
consistency, and the synthetic shadow demo passed. The demo retained source
hashes and produced the expected decision counts. The corrected source freeze
reverse-applies in check-only mode against the working source.

The manifest's `current_review_patch` identifies this corrected freeze, including
the narrow fork-publication workflow guard. `third_review_rejected_patch` retains
the prior rejected freeze. Historical failed verdicts and prior check results
are preserved rather than relabeled as passing reviews.

A read-only candidate review found floor-division, repeated-field, alias, and
additional JavaScript cases. They were reproduced and added as regressions in
the correction. This is not a new independent approval of the full final patch,
and it is not the separately requested Claude review.

## Git integration

The fork originally had no `main`; its default branch was `develop`. The new
`main` starts at upstream v3.11.0 plus a narrow CI guard that prevents fork pushes
from publishing Docker images. The source branch is
`fix/opaque-transcript-ingestion`. The existing `develop` and repository default
branch are retained. No tag, package release, production deployment, service
change, or real-data ingestion is part of this publication.

The first PR CI attempt passed lint and version checks but could not install
Python 3.9 on `ubuntu-latest` (Ubuntu 26.04), cancelling the other Linux matrix
entries. The Python 3.9 entry now uses Ubuntu 24.04; other versions retain
`ubuntu-latest`. This fixes runner compatibility without changing application
code or reducing the test matrix.

The final commit/PR/merge identifiers and observed CI status are recorded in
`PUBLICATION_RECEIPT.md` after the remote operation succeeds.

## Remaining limits

The full upstream suite was not rerun; its previously attempted collection was
blocked by missing Hypothesis in the isolated environment. Selected integration
does not certify all platforms, real-model extraction, or deployed transport.
The requested Claude review remains separate and was not run here. GitHub CI
status must be read from the receipt or PR rather than inferred from local tests.

Accepted replacements can still delete old records before a later write fails,
and some writer routes remain ungated. These remain deployment blockers.
Failure injection on disposable data must establish replacement safety before
valuable reingestion; a backup or rollback promise is not proof.
