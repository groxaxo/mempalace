# Pre-publication preservation fixes

These are recorded local command outputs, not fabricated examples. Local home,
workspace and tool-cache prefixes are redacted. The manifest maps original and
published hashes. The original 64-artifact implementation archive remains
separate; this folder captures the later failed-review corrections.

- `01-markers-red-assertions.txt`: 26 expected assertion failures before the
  marker fix; `01-markers-green.txt`: the corresponding 26-case pass. The earlier
  `01-markers-red*.txt` attempts are retained transparently; the initial runs
  had keyword-only writer-call and conversation success-sentinel mistakes,
  corrected before the authoritative assertion-failure run.
- `02-parse-errors-red.txt`: 22 failures and 38 passing controls before the
  source-literal fix; `02-parse-errors-green.txt`: 60 passing controls.
- `02-js-literals-red.txt` and `02-js-literals-green.txt`: the later complete-JS
  key/constant boundary slice. It was added before implementing support.
- `03-focused-new-green.txt` / `04-safeguards.txt`: intermediate results before
  the final JS/malformed-numeric controls; they are not the final counts.
- `05-focused-final.txt`: 92 publication-review regression cases passed;
  `05-safeguards-final.txt`: all 176 safeguards passed. Negative controls cover
  supported incomplete transcript families and typed/malformed transports.
- `05-tool-format-compatibility.txt`: direct legacy-display formatter check;
  `06-tested-source-sha256.txt`: fix-agent final source fingerprints.
- `REPORT.md`: path-redacted fix-agent report. Agent-reported evidence is
  distinct from independently captured parent checks.
- `parent-integration.json`: parent-run **619 passed** (176 safeguards plus
  443 affected upstream cases). `parent-ruff_check.json`,
  `parent-ruff_format.json`, `parent-compileall.json`, and
  `parent-shadow_demo.json`: parent checks of the same source tree; all exited
  zero. Full upstream suite/CI, real-model and live MCP coverage are not claimed.

Commands used synthetic fixtures, offline settings, embedding/storage spies
and disposable workspace-local data. No production indexing, archival copy,
reingestion, database mutation, restart or deployment was performed.

The initial failed independent verdict is `../INITIAL_REVIEW.json`. Its
findings must not be hidden behind the earlier 527-case pass. Re-review of the
current full patch and the separately blocked requested Claude review are
tracked by `../PUBLICATION_CHECKS.json` and `../CLAUDE_REVIEW_HANDOFF.md`.
