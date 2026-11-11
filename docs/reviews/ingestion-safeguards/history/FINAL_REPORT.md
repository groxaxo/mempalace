Implemented locally against the deployed MemPalace 3.11.0 snapshot at `88222ec8be25295c6ea2155ee6cdcf89c58e58fd`. The original commit remains intact; all changes are uncommitted. No production service, palace, real transcript, SSH session, model download, provider setting, global configuration, deployment, reindex, commit, or push was used.

The patch adds shared deterministic admission in [mempalace/ingestion.py](../../../../mempalace/ingestion.py) and a read-only shadow command in [mempalace/ingestion_audit.py](../../../../mempalace/ingestion_audit.py). Recognized unsupported/incomplete/malformed transcript envelopes cannot fall back to serialized prose. Canonical Codex event messages still work; response items remain excluded. One format-specific JSON string layer is supported, with bounded diagnosis and refusal of deeper recognized encodings. This is structural ingestion control, not a semantic relevance classifier.

Typed selection removes encrypted reasoning and recognized image/audio/binary/raw-buffer transport data while retaining surrounding text, command errors, and useful structured tool evidence. It never decrypts or base64-decodes data. Ordinary prose, configuration JSON, source code, hashes, multilingual facts, and fenced technical examples have positive controls. Unknown schemas and payloads disguised as ordinary prose remain outside the guarantee.

The conservative defaults are an 8 MiB admission budget, 256 KiB tool-input string budget, bounded tool-tree traversal (4,096 visits / depth 12), and formatted tool-result limits of 512 UTF-8 bytes per line and 2,048 bytes total. Standalone, varied base64-alphabet spans of at least 2,048 characters are omitted outside code fences; typed transport fields are selected structurally regardless of that span rule. Oversized tool results are omitted with reason counts. Oversized sources are unsupported. The conversation/audit reader also caps the actual read; the project reader retains its deployed read limit and applies admission after reading. These budgets deliberately narrow large-file acceptance and require review before enablement.

Omission reasons/counts travel in primitive storage metadata (`ingestion_policy`, `ingestion_decision`, `ingestion_reasons`, `ingestion_omissions`). Human-readable markers are removed before chunking/indexing, including protection against markers split by size limits. Source paths and document/metadata/id/vector alignment are retained. Project line locators are withheld after transformation because normalized offsets are not original source lines. Normalization/chunker versions were not bumped, so this patch does not schedule a bulk refresh of existing rows.

The protected scope and its evidence are:

| Path | Admission boundary and tested scope |
| --- | --- |
| `normalize.normalize` / `normalize_conversations` | Shared source admission, Codex headerless/malformed/incomplete envelopes, quote bypasses, bounded encoding, Claude/message/bundle/Gemini/Pi recognition, typed content, and positive controls. Recognition is conservative and format-specific. |
| `convo_miner._normalize_convo_conversations` → `chunk_exchanges` → `_file_chunks_locked` | Admission before fragmentation, then batch validation before lock/purge. Refused/empty sources produce no refresh registry row. Empty or partially rejected replacement batches preserve existing rows. Source provenance survives chunking. Already admitted chunks retain their source context so a fenced example is not reinterpreted as a transcript fragment. |
| `miner.process_file` | Project `.json`/`.jsonl` cannot bypass source admission. Supported transcripts are normalized before chunks, embeddings, deletion, or closet generation. Tested with storage and embedding spies and real project chunking. |
| `miner.add_drawer` / `convo_miner.file_conversation_exchange` | Manual compatibility and live exchange inputs use the same classifier. Rejection writes nothing; sanitized facts retain sources and provenance. Extra live metadata cannot override admission metadata. |
| MCP `tool_add_drawer`, `tool_update_drawer`, `tool_diary_write`, `tool_checkpoint` | Admission before WAL previews, writes, destructive closet purge, and checkpoint duplicate-query embedding. Sanitized adds remain idempotent. Metadata-only changes to legacy content requiring sanitization/refusal require explicit replacement content; a no-op still does no write. Real handler fragments were executed using the package's exec-loading convention, without starting a transport. |

The inspected hook route uses conversation mining, and Hermes uses the live exchange function. Those routes inherit these function-level controls; hook subprocesses, Hermes transport, MCP server startup, and model-based general extraction were not run end to end. Conversation general extraction receives admitted source text, but generated extraction output was not validated with a real model. The chunk helper's optional source metadata is an internal caller contract, not a security boundary against arbitrary callers inventing metadata or prefragmenting payloads.

Remaining writers are explicitly unprotected by this patch:

| Writer | Remaining work |
| --- | --- |
| `diary_ingest.ingest_diaries` | Daily Markdown files have separate entry, state, drawer, and closet rebuild logic. Add per-entry/source admission with state and pre-purge preservation tests before enabling it for transcript-derived data. MCP diary writes are covered separately above. |
| `format_miner._file_chunks_locked` / format extraction | Extracted document text and refresh/skip registration need their own source-level admission and replacement tests. |
| `sweeper.sweep` / `sweep_directory` | Separate Claude parser/flattening and direct upserts bypass the guarded miner. |
| `sources.context.PalaceContext.upsert_drawer` and adapters using direct collections | Adapter records and prefragmented content can bypass source classification. |
| `media.store_media_asset`, CLI `cmd_compress`, migration, repair, direct backend/embedding calls | These have different content/vector/update contracts and were not rewritten or certified here. Knowledge-graph/logstream writers are also outside this document-ingestion patch. |
| `deployment_reference` adapters | Reference-only files remain unchanged. Their length-safe embedding logic is not an admission gate. |

These staged paths need their own safe fixtures and behavioral coverage; no safe-coverage claim is made for them. In particular, filtering all storage documents indiscriminately would risk idempotency and document/vector alignment. Unknown envelopes, quoted/fenced examples, short or low-diversity opaque-looking text, and arbitrary payloads embedded in otherwise ordinary prose are not universally detected. Reason counts describe implemented omissions, not a complete accounting of every field skipped by every legacy parser.

The runnable shadow demonstration is:

```bash
TMPDIR="$PWD/test-tmp" .venv/bin/python scripts/shadow_demo.py
```

It creates only synthetic files under `test-tmp/shadow-demo`, runs the actual audit CLI, and checks source hashes remain unchanged. The recorded final run classified **1 keep, 3 sanitize, 1 archive-only, 1 unsupported**; see [evidence/FINAL_SHADOW_DEMO.txt](evidence/FINAL_SHADOW_DEMO.txt). To classify explicitly supplied files without generating fixtures:

```bash
TMPDIR="$PWD/test-tmp" .venv/bin/python -m mempalace.ingestion_audit path/to/file.jsonl path/to/notes.md
```

Output contains decisions, fixed reason codes/counts, omission counts, selected sizes, and source references; successfully read files also have exact-byte SHA-256 fingerprints. It prints no source contents, creates no archives, rejects symlinks/nonregular inputs, and imports no palace/configuration/embedding/Chroma code. `archive-only` means leave the original source in place and skip indexing, not copy it elsewhere. The shadow command never opens or writes a palace. Guarded writers use these defaults when this local code is invoked; the audit itself only reports.

Validation used the existing repository venv and synthetic disposable data with `TMPDIR` inside this workspace. Network connections, service discovery, and configured model construction are blocked in tests. The actual `EmbeddingCollection` wrapper delegates to a spy embedding boundary and storage spy; no real Chroma database or Nemotron service was used. The installed distribution did **not** include the upstream test suite; the complete available suite here consists of the newly added behavioral tests. No real-model, production, retrieval-quality, or benchmark result is claimed.

| Final check | Actual result and evidence |
| --- | --- |
| `.venv/bin/python -m pytest -q` | **84 passed**; [FINAL_PYTEST.txt](evidence/FINAL_PYTEST.txt) |
| `.venv/bin/python -m compileall -q mempalace tests scripts deployment_reference` | Exit 0; [FINAL_COMPILEALL.txt](evidence/FINAL_COMPILEALL.txt) |
| `git diff --check` | Exit 0; [FINAL_DIFF_CHECK.txt](evidence/FINAL_DIFF_CHECK.txt). New files are checked separately in [NEW_FILES_DIFF_CHECK.txt](evidence/NEW_FILES_DIFF_CHECK.txt). |
| Exported patch reverse-application check with whitespace errors enabled | Exit 0; [FINAL_PATCH_CHECK.txt](evidence/FINAL_PATCH_CHECK.txt). Check only; no patch was applied. |
| Unchanged reference adapters, storage backends, search code/settings, normalization/chunker versions | Exit 0; [UNCHANGED_BOUNDARIES.txt](evidence/UNCHANGED_BOUNDARIES.txt) |

The vertical red/green commands, expected failures, and passing outputs are retained under [evidence/tdd](evidence/tdd), with an [index](evidence/TDD_INDEX.md). Additional positive/preservation checks and intermediate fixture failures are retained honestly under `evidence`. Review the five modified deployed source files, two new ingestion modules, `tests/`, `scripts/`, this report, and the exported [implementation patch](evidence/IMPLEMENTATION.patch). The patch export includes new implementation/tests/report files without modifying Git's index; original untracked workspace instructions and `.gitignore` are preserved.

The remaining replacement hazard is material: admitted conversation/project refreshes still purge old records before replacement embedding/upsert. An embedding/storage failure can therefore lose the old rows. Admission rejects before that boundary and never marks refusal as a successful refresh, but does not make accepted replacements atomic. This finding is not evidence of a live deletion incident. Failure-safe replacement, with tested failure injection and old-generation preservation, is a deployment prerequisite before any reingestion; backups alone are insufficient.

Search thresholds/settings remain unchanged. Index cleanup does not solve nonsensical query matches or justify a universal distance cutoff. Calibrated query relevance/abstention on representative labeled queries remains a separate follow-up; the counterexamples supplied in TASK.md were not re-benchmarked here.

A cautious deployment proposal, not an action taken: review the patch and rejection samples; recover/run the upstream suite when available; test staged writers and the deployed adapter against a disposable copied palace with embedding/storage failures; implement failure-safe replacement; then run shadow classification on explicitly approved sources. Consider enabling only covered new/changed-write routes initially, with no normalization-version bump or automatic reingestion. Any later cleanup needs separate review and authorization. Rollback would restore the prior code release and stop guarded ingestion; additive metadata remains readable. Code rollback cannot restore rows lost by a later replacement, so restoration and failure-safe replacement must be proved separately before deployment.
