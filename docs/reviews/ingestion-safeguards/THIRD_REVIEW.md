# Final independent review: failed; publication blocked

The final fresh independent `gpt-6.1-sol` reviewer rejected the complete frozen
source/tests/scripts patch, SHA-256
`259ebac8330ba368035ac096962573ca0d5bbc6e47b8de61a40e92631154ef50`.
The review completed on 2026-11-11. This is not the requested Claude review.

The complete delayed verdict is now preserved in [THIRD_REVIEW.json](THIRD_REVIEW.json):
**one security finding (R1) and four logic findings (R2–R5)**. Its reviewed patch
digest matches the frozen patch above. This is the delivered `deleg_1bb66552`
review, dispatched on 2026-11-11 at 15:03:31, not a new fix or a later passing
review. The manifest records the captured/public JSON hashes; no content
redaction was needed.

The preliminary record relied on a completed-task log that truncated individual
assistant chunks and its final summary. That log's SHA-256 was
`65bdae5a539ca2dad9ace427889434cca968519bf57af7ea61a642c4c14741f9`.
The full delivered JSON supersedes the partial finding extraction, not the
failed disposition. Reviewer observations below remain separate from the
parent's independent reproduction.

## Parent-confirmed security blocker

The reviewer reported P1 memory exhaustion in `mempalace/ingestion.py:117-157`
(literal recognition), reached through admission, whose exception handling at
lines 660-663 does not contain `MemoryError`.

The parent independently reproduced the failure with synthetic inputs of the
following fixed shape, without loading a model or opening a storage client:

```python
text = '[{"rawOutput":{"base64":0}},' + '0,' * n + ']'
result = admit_text(text, spellcheck=False)
```

Each probe ran in a separate offline subprocess with a 128 MiB address-space
limit, 4/5-second CPU limits, an 8-second alarm and a 12-second parent timeout.
Socket creation was blocked and bytecode writes were disabled. Actual results
are in [`review-second-fixes/parent-memory-blocker.json`](review-second-fixes/parent-memory-blocker.json):

| Repetitions | Input bytes | Outcome | Observed peak RSS (KiB) |
| --- | --- | --- | --- |
| 20,000 | 40,029 | keep | 40,104 |
| 60,000 | 120,029 | keep | 79,568 |
| 120,000 | 240,029 | MemoryError escaped admission | 102,104 |

All inputs are below the 8 MiB source limit; the failing input is also below the
256 KiB tool input limit. The limit is virtual address space, not an RSS limit;
peak RSS need not equal 128 MiB when allocation fails. These are bounded local
observations, not hardware-independent benchmarks or measurements of an
unrestricted production process. The failure demonstrates uncontrolled parser
allocation and an uncaught exception, not proof that the host OOM killer ran.

Catching `MemoryError` alone or raising limits is not sufficient hardening.
Recognition needs an explicit, enforced work/allocation budget before expensive
AST construction while preserving useful ordinary source, JSON and prose.

## Complete logic finding index

These are the independent reviewer's bounded observations on the matching
frozen patch; this receipt does not claim a new parent test run.

- **R2 / P1 — incomplete-envelope fallback** (`ingestion.py:512-552`): root
  role/content messages, ChatGPT mappings, Slack messages and identifying fields
  after the 2,048-character prefix can remain indexable raw envelopes. Exhausting
  recognition's budget must not authorize raw fallback.
- **R3 / P2 — lexical-boundary false refusals** (`ingestion.py:527-551`): apparent
  envelope fields inside Python/JavaScript comments or Python triple-string data
  can wrongly trigger `unparsed_codex`. Recognition must respect lexical scope
  and structural depth without allowing actual root envelopes through.
- **R4 / P2 — valid JavaScript false refusals**
  (`ingestion.py:107-109,129-157,204`): Unicode property identifiers and template
  literals pass syntax checking but are discarded by admission and formatting.
- **R5 / P2 — fenced literal deletion** (`ingestion.py:264-283`): a shorter
  backtick run inside a four-backtick fence, or a tilde run inside a backtick
  fence, wrongly exits fenced mode and permits deletion of literal source data.
  Track the opening delimiter character and run length.

[THIRD_REVIEW.json](THIRD_REVIEW.json) preserves all reproductions, evidence,
impacts and requested changes. Its probe timings/resource observations are
reviewer-specific; the parent memory table above is separately measured.

## Decision

The older review's complete delayed verdict is now available in
[SECOND_REVIEW.json](SECOND_REVIEW.json), with chronology and all five findings
in [SECOND_REVIEW.md](SECOND_REVIEW.md). That result is not a new review of this
freeze. Any authorized next pass must reconcile its first-record truncation and
Continue final-byte-cap findings too; the CPU/triple-quote correction's GREEN
records cannot establish that all older findings were addressed.

- **Publication remains blocked. No commit, push, deployment, service restart,
  historical cleanup or production write was performed.**
- Both permitted automatic correction cycles have been used. Stop the automatic
  fix loop and escalate the remaining parser-design/security issues to the user
  before another correction attempt.
- The 672 selected passing tests and successful lint/format/compile/demo checks
  describe the tested scenarios; they do not override this failed review.
- Parent fingerprint verification found no mismatch in the 18 frozen
  source/tests/scripts files after the bounded reproduction.
- Claude Sonnet 5.5 / medium remains separately authentication-blocked.
