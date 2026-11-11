# Ingestion safeguards: review and evidence

This is a **review-only publication**, not a deployment approval. Start with the
[user-facing scope and commands](../../ingestion-safeguards.md).

## Branch base and contents

- Repository: `groxaxo/mempalace`; source branch:
  `fix/opaque-transcript-ingestion`; integration target: `main`.
- Base release: upstream `v3.11.0`, commit
  `602d796c699cabba2971982cd9dccbbf46abfe79`. The separate annotated-tag object
  is `208df468b0ee5c27028d7bf42cea619a0237e88c`; it is not the base commit ID.
- All 169 deployed package snapshot files matched that release before the
  patch. The fork's older `develop` is deliberately not advanced or rewritten.
- Seven production files carry the implementation. Initial publication staging
  was Ruff-formatted and AST-equivalent to the delivered snapshot; subsequent
  pre-publication review corrections are identified separately in the manifest.
- The original 84-case suite lives in `tests/ingestion_safeguards`, alongside
  publication-review regressions. Offline restrictions are scoped there.
  Upstream `tests/conftest.py` is untouched.
  The MCP-fragment fixture's root locator is adjusted for nesting, and its
  shared-fixture import is an explicit re-export for Ruff.
- `scripts/shadow_demo.py` and `scripts/record_check.py` are included. Disposable
  `test-tmp/` fixtures and test homes are ignored by Git.
- `history/` preserves 64 implementation reports, patch/manifest, red/green
  logs, parent checks, and the blocked-review handoff. Local workspace/private
  host references in 57 copies are redacted. These are historical evidence,
  not commands to run against this checkout or a production service.

The provenance mapping in [PUBLICATION_MANIFEST.json](PUBLICATION_MANIFEST.json)
records both the original and published hashes and flags redacted artifacts.
The frozen implementation patch is historical; formatting and relocated tests
mean it is not a reverse-apply check for the publication tree. Original snapshot
hashes in the historical manifest are not this branch's source hashes.

## Verification in the actual publication checkout

The original standalone snapshot passed 84 synthetic tests. After recovering
upstream source/tests, publication verification established a release baseline
and exercised the integrated tree. Details and exact commands are recorded in
[PUBLICATION_CHECKS.json](PUBLICATION_CHECKS.json).

1. Unmodified upstream release: **443 passed** across seven affected upstream
   modules with `TZ=UTC`. Without that setting, one pre-existing mtime/date test
   failed because its timestamp falls on the following date in the host timezone.
2. Initial integration: **519 passed, 8 failed** across those modules plus the
   new 84 cases. The failures exposed intentionally changed policy contracts;
   they were not suppressed, deselected, or hidden by fixture replacement.
3. Pre-review integration: **527 passed**. At this stage all seven production
   modules retained the original implementation's AST. The upstream test
   changes are explicit:
   - Bash/Grep/Glob omission strings now use fixed provenance markers.
   - Unknown tool output is checked against the UTF-8 line-byte cap instead of
     the former character-count suffix.
   - Continue tool messages use the shared formatter's arrow prefix.
   - The low-level ChatGPT parser still declines malformed mappings. Dispatch
     now refuses the recognizable malformed envelope while unrelated mapping
     JSON remains a valid fallback control.
   - Oversized sources raise `NonIndexableContentError` with
     `source_byte_budget` / `unsupported`, not the old 500 MiB `IOError` contract.
   - The directory-identity wiring fixture now contains a supported two-turn
     session. Its former one-turn input reached storage only via raw-envelope
     fallback. A normalizer test explicitly asserts refusal of that incomplete
     envelope, rather than weakening the fail-closed policy to make it pass.

4. Independent review reproduced two preservation defects; the publication adds
   **92 regression cases** with RED/GREEN evidence. Parent integration after
   that first correction: **619 passed**, comprising 176 safeguards (the original
   84 plus 92 review regressions) and 443 affected upstream cases. This is now a
   historical result: [the second review failed](SECOND_REVIEW.md). Its complete
   [delayed verdict](SECOND_REVIEW.json) contains two security and three logic
   findings, including CPU/memory exhaustion, first-record truncation, triple-quoted
   literal preservation and Continue's post-cap label. Generated annotations are
   separate from selected text, while literal marker strings remain content.
   The old literal-marker-only rejection assertion was corrected; genuinely
   omission-only input still produces no selected text or writer mutation.

Only the described policy-specific expectations and wiring fixtures were
adapted; production admission behavior was not loosened for compatibility. Incomplete
sessions remain eligible for retry when later completed, not guaranteed to be
partially recalled. Full upstream suite/coverage, platforms, live MCP transport,
and real-model extraction were not certified by the historical 672-case run. The
527-case pass is historical and predates the review findings. Full-suite
collection was attempted but stopped on two modules importing the missing
`hypothesis` development dependency. The checks reused the isolated snapshot
Python environment; no live installation was changed. Ruff check passed for the
whole checkout, Ruff format reported 401 already-formatted files, compilation
passed, and the read-only synthetic shadow demo produced the expected counts.

## Pre-publication independent review

The initial independent review failed on two preservation defects despite the
527-case pass: regex-based marker removal deleted legitimate literal examples,
and field-name-only malformed-transport detection rejected valid source-code
literals. [INITIAL_REVIEW.json](INITIAL_REVIEW.json) records the findings. These
are implementation defects, not deployment-risk waivers. The original snapshot
reports and earlier green counts are historical and do not establish that
these scenarios worked. This review is distinct from the requested Claude
Sonnet 5.5 / medium review, which remains authentication-blocked.

## Second correction and current verification

The second correction adds 53 regressions for tokenizer CPU exhaustion and
complete Python triple-quoted literals. Parent checks on the frozen, stable
source passed **672 selected cases**: 229 safeguards (84 original + 92 first
review + 53 second review) and 443 affected upstream cases. Lint, formatting,
compilation, and the synthetic shadow demo also passed. See
[`review-second-fixes/README.md`](review-second-fixes/README.md) for actual
RED/GREEN logs and separately captured parent checks.

The final independent review of the entire final source/tests/scripts patch
**failed**, including a P1 memory-exhaustion finding independently reproduced by
the parent. [THIRD_REVIEW.md](THIRD_REVIEW.md) and its complete delivered
[JSON verdict](THIRD_REVIEW.json) record R1 memory exhaustion and R2–R5
incomplete-envelope fallback, lexical false refusals, unsupported valid JS
literals and fenced literal deletion. **Publication is blocked; no commit or push was
made.** Both automatic correction cycles were exhausted at that point. Neither
672 selected passes nor the historical 527/619 results approved that tree.
Claude authentication remains unavailable; no
substitute review is represented as the requested one.

## User-authorized third correction

The subsequent working correction addresses R1–R5 in `ingestion.py` and
`normalize.py`, with 61 new cases in
`tests/ingestion_safeguards/test_review_third_fixes.py` (290 safeguards total).
It bounds syntax before parser allocation and parses only the transformed
literal candidate, avoiding Python/JavaScript comment ambiguity. Envelope
recognition uses lexical root structure for complete and truncated inputs,
retains repeated-field evidence, and preserves existing message aliases.
Unicode identifiers, template strings/interpolations, and Markdown fence
delimiter/length controls exercise admission, formatting, and writer behavior.

The candidate review identified additional floor-division, repeated-field,
alias, and JavaScript syntax cases; these were reproduced and added to the same
correction. That review is distinct from the authentication-blocked Claude
review and does not establish independent publication approval. The user then
authorized committing, pushing, and merging the corrected candidate into the
fork's `main`. [THIRD_CORRECTION.md](THIRD_CORRECTION.md) records the current
correction and validation. The manifest's `current_review_patch` identifies the
corrected source freeze; `third_review_rejected_patch` retains the prior freeze.
`PUBLICATION_CHECKS.json` keeps the old checks alongside the current evidence.
Accepted replacement safety and uncovered writers remain deployment blockers.

Final selected integration passed **733 cases**: 290 safeguards and 443 affected
upstream cases, with `TZ=UTC` and the existing offline/disposable test setup.
Whole-checkout Ruff check/format, compilation, and the synthetic shadow demo
passed. Fourteen JavaScript controls passed Node's syntax check without source
execution; 384 complete-JSON controls matched the family predicates. This is
selected integration evidence, not a full upstream suite or a new publication
approval. Hypothesis remains absent from the isolated environment; the earlier
whole-suite collection and separately requested Claude review were not rerun.
The guarded subprocess probes now run only on Linux; the portable controls
remain enabled on other platforms. CI configuration prevents this fork's `main`
pushes from publishing container images. The existing `develop` branch and
repository default branch are left unchanged.

## Historical evidence map

The first publication-review fixes and separately captured parent output live
in [`review-fixes/`](review-fixes/README.md); the later failed re-review is
recorded in [SECOND_REVIEW.md](SECOND_REVIEW.md). Semantic fixes are
identified in the manifest and are not claimed AST-equivalent to the original
snapshot. [`CLAUDE_REVIEW_HANDOFF.md`](CLAUDE_REVIEW_HANDOFF.md) applies to the
current publication tree, not the earlier frozen historical patch.

- [Implementation report](history/FINAL_REPORT.md): original design, coverage,
  examples, limits, and residual risks; it predates recovery of upstream tests.
- [Frozen patch](history/evidence/IMPLEMENTATION.patch): original snapshot
  implementation, tests, scripts, and report.
- [TDD index](history/evidence/TDD_INDEX.md): 18 vertical cycles, including the
  corrected malformed-ID red case, marker probes, and storage-spy caveat.
- [Parent verification](history/evidence/INDEPENDENT_VERIFICATION.txt): separate
  original-snapshot test, compilation, patch, and shadow-demo checks.
- [Original manifest](history/evidence/REVIEW_MANIFEST.json): earlier baseline,
  runtime versions, and source fingerprints; use the publication manifest for
  the current source mapping.
- [Requested review handoff](history/evidence/CLAUDE_REVIEW_HANDOFF.txt): the
  requested Claude Sonnet 5.5 / medium review remains authentication-blocked.
  No parent checks or different reviewer should be presented as that review.

Local task/agent instructions, authentication stores, raw agent transcripts,
deployed-package metadata, private adapters/configuration, and generated test
palaces are intentionally not published. They are not implementation changes
and are not appropriate public repository contents. The original local workspace
and frozen patch remain available separately.

## Deployment is still blocked

Accepted-replacement delete-before-write exposure and uncovered writers remain
explicit blockers. Passing rejection-preservation tests does not establish
atomic replacement. No production cleanup, reingestion, restart, MCP
registration, provider-setting change, or deployment accompanied publication.
