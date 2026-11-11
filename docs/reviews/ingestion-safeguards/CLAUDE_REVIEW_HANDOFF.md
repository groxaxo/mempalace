# Requested Claude review — current publication handoff

Status: **blocked**, not completed. The intended local Claude client reports
`loggedIn: false`, `authMethod: none`, and `apiProvider: firstParty`. Existing
Codex authentication is not Anthropic authentication. No substitute review is
represented as the requested **Claude Sonnet 5.5 / medium** review.

## Unblock locally

Run `claude auth login` using the intended Anthropic account on the review
computer. Do not paste tokens/passwords into chat or add auth files to this
repository. Verify `claude auth status` before running a review. Confirm the
exact available model identifier for Claude Sonnet 5.5; do not silently use a
moving alias, a different model, or an automatic fallback. Request medium
reasoning and verify the model actually used in the returned `modelUsage`.

## Review the current tree, not the historical snapshot

1. Read [`../../ingestion-safeguards.md`](../../ingestion-safeguards.md),
   [`README.md`](README.md), [`INITIAL_REVIEW.json`](INITIAL_REVIEW.json),
   [`SECOND_REVIEW.md`](SECOND_REVIEW.md),
   its complete delayed [`SECOND_REVIEW.json`](SECOND_REVIEW.json),
   [`THIRD_REVIEW.md`](THIRD_REVIEW.md),
   its complete delivered [`THIRD_REVIEW.json`](THIRD_REVIEW.json),
   [`review-second-fixes/README.md`](review-second-fixes/README.md), and
   [`PUBLICATION_CHECKS.json`](PUBLICATION_CHECKS.json).
2. Freeze the current production/tests/scripts diff relative to
   `602d796c699cabba2971982cd9dccbbf46abfe79` (the v3.11.0 release commit):
   `git diff 602d796c699cabba2971982cd9dccbbf46abfe79 -- mempalace tests scripts`.
   On the published branch, this includes all committed additions. Review all
   new files as well as modified ones, explicitly including untracked tests such
   as `tests/ingestion_safeguards/test_review_third_fixes.py` in a working-tree
   review. Fingerprint the diff and source files;
   the historical implementation patch is not the current publication patch.
3. Focus on preservation of literal omission-marker examples, separation of
   generated annotations from indexable text, normalizer joins and tool byte
   caps, and valid source literals versus recognizable malformed transport.
   Inspect tokenizer complexity on unterminated comments/quotes and preservation
   of complete Python triple-quoted literals containing comment delimiters.
   Check pre-AST allocation limits (including Python floor division), truncated
   and repeated envelope fields, lexical root boundaries, supported aliases,
   JavaScript Unicode/template syntax, and matching Markdown fences.
   Also check the full admission/writer policy and the regression controls.
4. Use a read-only client configuration: only `Read,Glob,Grep`, explicit empty
   MCP configuration with `--strict-mcp-config`, `--permission-mode dontAsk`,
   no session persistence, and no custom hooks/plugins/auto-memory. Confirm
   flags against the live CLI help; do not alter global settings or the
   MemPalace-only learned-memory policy.
5. Return concrete file/line findings, distinguish newly introduced defects
   from disclosed deployment blockers, and record the actual model, effort,
   patch/source fingerprints, and review limits with the verdict.

Review only: no production access, embeddings, indexing, reingestion, database
writes/deletes, restarts, deployment, MCP registration, authentication-store
inspection, or configuration changes. Parent-run tests must remain independent
of review-agent claims. Publication is not deployment approval; uncovered
writers and accepted-replacement delete-before-write remain blockers even if
this source review passes.
