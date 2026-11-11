# Ingestion safeguards (experimental review branch)

## Status and compatibility

This change is for review, **not cleared for production deployment**. The branch
is based on upstream `v3.11.0` (commit `602d796c699cabba2971982cd9dccbbf46abfe79`;
annotated tag object `208df468b0ee5c27028d7bf42cea619a0237e88c`).
All 169 files in the deployed package snapshot matched that release byte for
byte before applying the patch. The fork's older `develop` branch is not a
compatible drop-in base; publishing this branch does not replace that branch,
upgrade any service, or change a palace.

The guarded writers enforce admission when called. There is no global
shadow-mode switch or feature flag in this patch. Only the audit command below
is read-only. Package, normalization, and chunker versions are not bumped; this
patch does not itself schedule reingestion. The base release's existing upgrade
behavior still applies to any future upgrade from older releases.

## What is admitted

The [third review](reviews/ingestion-safeguards/THIRD_REVIEW.md) rejected the
previous frozen patch. The user-authorized working correction addresses R1–R5
with bounded parser allocation, lexical envelope recognition, Unicode/template
preservation, and matching Markdown fences. Its regressions also cover repeated
envelope fields and supported message aliases. The user authorized committing
and merging the corrected candidate into this fork's `main`. The corrected
freeze, selected checks, and publication record are linked from the
[review documentation](reviews/ingestion-safeguards/README.md); the prior verdict
and fingerprints remain historical. No new independent final-patch or Claude
approval is claimed.
The policy below describes tested scenarios, not universal coverage.

The policy is deterministic structural filtering, not a semantic relevance or
malware classifier. Recognized malformed, incomplete, unsupported, and
headerless transcript envelopes cannot become raw serialized prose through a
parser fallback. Canonical supported conversations remain supported. A bounded,
format-specific JSON string layer is handled; arbitrary recursive decoding is
not performed. A failed JSON parse plus a transport-related field name is not
sufficient evidence to reject source code. Complete JavaScript/Python literal
examples, including semicolons, trailing commas and comments, remain content;
recognizable incomplete transcript envelopes and typed transports still fail
closed. This distinction is structural, not a language-execution step.
Envelope recognition follows root structure through late fields and retains
evidence from ambiguous repeated fields. Comments, strings, and unrelated nested
configuration do not supply root transcript fields.

An incomplete Claude Code session with only one visible turn is refused until
it satisfies the parser's existing two-turn requirement. Previously that case
could fall through to raw JSON indexing. The source is preserved for retry;
this policy change is not a guarantee of partial-session recall.

Typed selection excludes encrypted reasoning, image/audio/binary payloads, and
recognized raw-buffer transport fields before flattening and chunking. It keeps
useful surrounding text and structured tool evidence, including command errors.
It does not decrypt or base64-decode content. Positive regression controls cover
ordinary prose, configuration JSON, source code, hashes/IDs, multilingual text,
and fenced technical examples.

Selected semantic text can differ from the original source: this is **not** a
new verbatim archival mechanism. Original input files are not modified; retain
them using your existing source-retention policy. Omitting a field from the
semantic index neither deletes nor archives the source.

| Decision | Meaning |
| --- | --- |
| `keep` | Useful text can proceed without this policy's sanitization. |
| `sanitize` | Useful selected text remains after normalization or omissions. |
| `archive-only` | No useful indexable text remains; skip indexing and leave the source in place. No archival copy is created. |
| `unsupported` | The recognized structure or resource limits cannot safely be handled; skip indexing. |

These are ingestion-quality outcomes, not relevance scores. Search settings and
similarity thresholds are unchanged. Historical index pollution and calibrated
query abstention are separate work.

## Resource limits and provenance

Defaults deliberately narrow large-input acceptance and require operational
review before enablement:

- Source admission budget: 8 MiB. The conversation/audit reader also caps reads;
  the project reader retains its existing read limit before applying admission.
- Tool-input string budget: 256 KiB, with bounded traversal (4,096 visits,
  depth 12).
- Serialized syntax budget: 16,384 lexical tokens and nesting depth 32 before
  JSON/literal parsing. Exhaustion returns `unsupported` with a fixed resource
  reason. Container AST parsing receives only a budgeted transformed candidate; source
  expressions and template interpolations are never executed.
- Formatted tool results: 512 UTF-8 bytes per line and 2,048 bytes total.
- Standalone, sufficiently varied base64-alphabet spans of at least 2,048
  characters are omitted outside literal code fences. Typed selection does not
  depend on this span heuristic.

Fixed reason codes/counts are retained as primitive storage metadata:
`ingestion_policy`, `ingestion_decision`, `ingestion_reasons`, and
`ingestion_omissions`. Generated omission annotations are kept out of admission's
selected text throughout formatting, joins, tool-size cuts, and covered writer
calls; they are not removed by matching source text against marker syntax.
Literal strings such as `[ingestion omitted: opaque_transport; count=1]` remain
source content, including in prose, fenced code, configuration, and mixed input
that also has real omissions. `indexing_text` trims selected text; it does not
classify or remove such literals. The legacy `normalize`,
`normalize_conversations`, and standalone tool formatter can render annotations
for display at their exits. Use `admit_text` and its metadata for ingestion;
do not feed a display-only rendering back as if it carried machine-readable
omission provenance. Source references and document/metadata/ID/vector alignment
are preserved. Project line locators are withheld after transformations because
the new offsets are not original source lines.

Unknown schemas, arbitrary opaque payloads disguised as ordinary prose,
short/low-diversity spans, and arbitrary callers inventing source-context
metadata are outside the guarantee. This is not a universal storage boundary.

## Covered write boundaries

| Route | Exercised boundary |
| --- | --- |
| `normalize` / `normalize_conversations` | Source admission and typed selection before fallback/flattening. |
| Conversation miner | Source admission before chunking and batch validation before lock/purge; rejected, empty, or partially rejected replacement batches preserve old records. |
| `miner.process_file` | Project files, including JSON/JSONL, are admitted before chunks, embeddings, deletion, and closet generation. |
| `miner.add_drawer` / `file_conversation_exchange` | Manual/live inputs share admission and retain provenance. |
| MCP add/update/diary/checkpoint | Admission precedes covered WAL, write/purge, and checkpoint duplicate-query embedding effects. Metadata-only updates of legacy content needing sanitization/refusal require explicit replacement text. |

Hook and Hermes routes were traced to the covered functions but were not run
end to end. MCP handler fragments are exercised without starting a transport;
real-model extraction was not certified.

## Remaining deployment blockers

1. **Accepted replacements are not atomic.** Conversation/project refreshes can
   still delete old records before embedding/upserting their accepted
   replacements. A later failure can lose the old rows. Rejection-preservation
   tests do not prove accepted-replacement safety. Implement failure-safe
   replacement and prove old-generation preservation with failure injection on
   disposable data before any valuable reingestion. A backup alone is not proof.
2. **Other writers remain ungated:** diary-file ingestion, format extraction,
   sweeper paths, `sources.context.PalaceContext.upsert_drawer`, direct collection
   adapters, media storage, compression, migration, repair, and direct backend
   calls. Knowledge-graph/logstream ingestion is outside this document policy.
3. The requested Claude Sonnet 5.5 / medium review has not run because intended
   local Anthropic authentication was unavailable. Parent verification is not
   that review. Full deployed transport/model tests, production shadow samples,
   retrieval-quality evaluation, and full upstream validation remain separate.

No production deployment, cleanup, reindexing, service restart, or provider
change was performed. Keep publication and deployment as separate decisions.

## Read-only audit

From a checkout with the package dependencies installed:

```bash
mkdir -p test-tmp
TMPDIR="$PWD/test-tmp" python -m mempalace.ingestion_audit path/to/session.jsonl path/to/notes.md
```

Supply files explicitly; the command does not discover directories or open a
palace. It rejects symlinks/nonregular inputs and reports JSON containing source
references, decisions, reason/omission counts, selected sizes, and exact-byte
SHA-256 fingerprints for successfully read files. It prints no source content
and imports no palace/configuration/embedding/Chroma code. Paths and source
hashes are still identifying metadata: review output before sharing it.

Unreadable inputs are represented by `unsupported` rows with a fixed reason;
process success is not approval to index every input. Consumers must inspect
`decision_counts` and individual rows.

The synthetic demo generates disposable files only under `test-tmp/shadow-demo`
and runs the real audit CLI. It checks that source hashes remain unchanged:

```bash
TMPDIR="$PWD/test-tmp" python scripts/shadow_demo.py
```

Expected counts: `keep=1`, `sanitize=3`, `archive-only=1`, `unsupported=1`.
Do not use the demo as a command for production ingestion.

## Reproduce checks

Use a local virtual environment; do not replace a live installation:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
mkdir -p test-tmp
export TMPDIR="$PWD/test-tmp" TZ=UTC
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ANONYMIZED_TELEMETRY=False
.venv/bin/python -m pytest -q tests/ingestion_safeguards
.venv/bin/python -m compileall -q mempalace tests/ingestion_safeguards scripts/record_check.py scripts/shadow_demo.py
.venv/bin/python scripts/shadow_demo.py
```

The synthetic cases use offline embedding/storage spies and disposable data,
not a real palace or model. The original 84-case suite is supplemented by
pre-publication review regressions (92 first-review, 53 second-review, and 61
third-review cases; 290 safeguard cases). These include CPU/address-space-limited
allocation probes, Python triple strings, JavaScript Unicode/template syntax,
truncated envelopes, and nested Markdown fences. The earlier 672 selected passes
describe the failed third-review freeze. Current verification and review limits
are described in the verification record. Their autouse restrictions live only under
`tests/ingestion_safeguards`; the upstream root `tests/conftest.py` is preserved.
The MCP-fragment test changes its repository-root locator for this nested
layout. Historical commands use the earlier isolated snapshot layout, not the
new test paths.

Recovered upstream tests can now be compared against the release baseline.
The original implementation report's statement that upstream tests were
unavailable describes the earlier installed-package snapshot, not this
checkout. `TZ=UTC` makes one existing mtime/date assertion deterministic on
hosts whose local date rolls into the next day. See the
[publication verification record](reviews/ingestion-safeguards/README.md) for
actual commands, results, adaptations, and current limitations. Do not infer a
full upstream/CI pass from a focused synthetic result.
