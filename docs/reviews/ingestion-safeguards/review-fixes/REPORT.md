Fixed the two requested content-preservation defects in this publication checkout.

Files changed by this fix agent:

- `mempalace/ingestion.py`: removed syntax-based marker deletion. Selected text and omission metadata now remain separate through formatting and byte bounding. Parse-error admission requires structural transport evidence or explicit tool context, while a non-executing literal probe recognizes complete JS/Python source without rewriting it.
- `mempalace/normalize.py`: renders compatibility annotations at display exits, after selection/joins/bounding. Admission and covered writers receive ordinary strings containing selected content only. Public normalizers still return `str` / `list[str]`.
- `tests/ingestion_safeguards/test_review_fixes.py`: 92 synthetic regression/control cases, including exact stored documents and omission/source metadata through live, manual, project-file, and conversation writer seams.
- `tests/ingestion_safeguards/test_ingestion.py`: moved the existing marker-fragment control to the actual admission/indexing channel; retained its fragment assertions and added byte-omission metadata assertions. The legacy display formatter intentionally renders complete annotations.

No writer implementation changes were required. No str subclass, randomness, or private-use sentinel supplies provenance. The Unicode preservation fixture includes private-use characters as literal source data.

TDD evidence, with actual command, environment, combined output, and exit status in every linked log:

| Behavior | Inspected RED | GREEN |
| --- | --- | --- |
| Literal markers and mixed real omissions | [01-markers-red-assertions.txt](01-markers-red-assertions.txt): 26 assertion failures, including deletion of the prose/config marker and archive-only treatment of a literal-only marker | [01-markers-green.txt](01-markers-green.txt): 26 passed |
| Parse-error source preservation plus refusal controls | [02-parse-errors-red.txt](02-parse-errors-red.txt): 22 failed / 38 passed; the supplied JS probes returned archive-only instead of keep | [02-parse-errors-green.txt](02-parse-errors-green.txt): 60 passed |
| JS single-quoted literals with constants/unquoted keys | [02-js-literals-red.txt](02-js-literals-red.txt): 3 assertion failures / 45 passed | [02-js-literals-green.txt](02-js-literals-green.txt): 48 passed |

The first two marker RED runs are also retained. They included test-call mistakes (keyword-only writer arguments and the conversation writer's success sentinel). These were corrected before implementation; the authoritative marker RED above contains only behavior assertion failures.

Final validation used `<snapshot>/.venv/bin/python`, with `TZ=UTC TMPDIR=<publication>/test-tmp HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`:

- `-m pytest tests/ingestion_safeguards/test_review_fixes.py -v --tb=short`: **92 passed**, exit 0. [Exact command/output](05-focused-final.txt).
- Then `-m pytest tests/ingestion_safeguards -v --tb=short`: **176 passed**, exit 0. [Exact command/output](05-safeguards-final.txt).
- `-m pytest tests/test_normalize.py -k format_tool_result -v --tb=short`: **13 passed, 148 deselected**, exit 0. These are existing pure synthetic formatter compatibility tests. [Exact command/output](05-tool-format-compatibility.txt).
- Existing Ruff **0.16.6**, found at `ruff`, checked/formatted only the four files above. [Lint: passed](05-ruff-check-final.txt). [Format check: 4 already formatted](05-ruff-format-check-final.txt).
- [Scoped `git diff --check`: exit 0](05-diff-check-final.txt).

Controls cover malformed typed raw buffers, numeric byte payloads, thinking/image payloads, and incomplete/malformed Codex, Claude Code, Claude.ai, ChatGPT, Gemini JSON/JSONL, Pi, Continue, and Slack inputs. They assert refusal before storage deletion/writes/embedding. Existing safeguards retain UTF-8 tool byte caps and nonindexable opaque-only input. New preservation cases cover prose, fences, config, literal-only markers, identical literal/generated marker syntax, comments/trailing commas, and JS/Python literals.

Limitations and workspace observations:

- The full upstream suite was not run. `hypothesis` is absent in the exact environment; its local-only `05-environment.txt` check is not published. The parent collection blocker is recorded in `../PUBLICATION_CHECKS.json`. No full-suite pass is claimed and no packages were installed.
- The global staged-patch digest changed concurrently. The initial equality check failed and its actual output is retained locally in `05-workspace-preservation.txt` (not published). This agent issued no staging/index mutations. Read-only observation shows earlier fix snapshots and the new tests were staged during this run; the final JS-literal additions were still unstaged at observation time. All concurrent state was left intact. Local-only follow-up records `06-workspace-observation.txt` and `06-status.txt` are not published; no linked public artifact is implied.
- The historical-artifact tree had no unstaged changes in the preservation observation. This agent did not edit publication docs, manifests, scans, or historical artifacts. Concurrent documentation work was left intact.
- No commit, push, deployment, model/service/MCP contact, auth inspection, global configuration change, or production `~/.mempalace` access was performed. Safeguard tests use the existing offline boundaries and synthetic storage/embedding spies.
