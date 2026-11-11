# Second review-fix evidence

This directory contains sanitized actual outputs from the second correction
cycle. Private filesystem prefixes are replaced with `<publication>`,
`<snapshot>`, `<local-home>` or `ruff`. Commands retain their arguments, outputs
and real exit statuses. Source and published hashes are mapped in
[`../PUBLICATION_MANIFEST.json`](../PUBLICATION_MANIFEST.json).

## CPU-exhaustion slice

- [`01-a-red.txt`](01-a-red.txt): **10 expected failures, 10 passing controls**.
  The repeated unterminated block-comment probe exhausted its finite CPU budget;
  it did not run an unbounded large payload.
- [`01-a-green.txt`](01-a-green.txt): **20 passed**, including the same bounded
  probe. Deterministic token-coverage controls require a single whole incomplete
  lexeme rather than repeated suffix scans; complete comments and quoted
  delimiters remain accepted.
- [`01-a-existing.txt`](01-a-existing.txt): **151 prior focused cases passed**.

## Python triple-quoted literal slice

- [`02-b-red.txt`](02-b-red.txt): **10 expected failures, 23 passing controls**
  (20 first-slice cases deselected).
- [`02-b-green.txt`](02-b-green.txt): **33 passed** (20 deselected), including
  complete quoted/comment delimiters and project-writer byte preservation,
  metadata, invalid-literal/no-execution and recognized-envelope controls.
- [`02-b-existing.txt`](02-b-existing.txt): **151 prior focused cases passed**.

## Final and parent verification

**The final independent review failed.** The parent reproduced uncontrolled
parser allocation and an escaping `MemoryError` despite the selected test
passes below. See [`../THIRD_REVIEW.md`](../THIRD_REVIEW.md) and the actual
[`parent-memory-blocker.json`](parent-memory-blocker.json) probe output.
These GREEN records are scenario evidence, not publication or deployment approval.

[`REPORT.md`](REPORT.md) is the sanitized implementing-agent report, not
independent approval. [`FROZEN_SOURCE.patch`](FROZEN_SOURCE.patch) is the exact
complete final source/tests/scripts review freeze, including the new test.
Its SHA-256 is
`259ebac8330ba368035ac096962573ca0d5bbc6e47b8de61a40e92631154ef50`.

- [`03-safeguards.txt`](03-safeguards.txt): **229 passed**, including the
  original 84 safeguards, 92 first-review regressions and 53 second-review cases.
- [`03-ruff-check.txt`](03-ruff-check.txt) and
  [`03-ruff-format-check.txt`](03-ruff-format-check.txt): final changed-file checks.
- [`04-final-verification.txt`](04-final-verification.txt) is an actual failed
  workspace-assumption check: the parent had changed its own publication JSON.
  [`04-final-verification-corrected.txt`](04-final-verification-corrected.txt)
  records this observed parent change without pretending it was agent-owned;
  prior controls and the staged index were unchanged by the implementing agent.
- [`parent-integration.json`](parent-integration.json): **672 passed** = 229
  safeguards + 443 affected upstream cases. Parent source fingerprints were
  unchanged before/after this run and match the frozen review patch.
- The `parent-ruff_check.json`, `parent-ruff_format.json`,
  `parent-compileall.json`, and `parent-shadow_demo.json` files preserve the
  independently captured checks; formatting found **401** formatted files.

These passes do not establish complete upstream validation (missing Hypothesis),
production transport/model coverage, safe accepted replacement, or deployment
approval. The separately requested Claude review remains authentication-blocked.
