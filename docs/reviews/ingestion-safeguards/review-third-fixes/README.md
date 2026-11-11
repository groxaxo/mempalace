# Corrected third-review candidate

The JSON files retain actual check commands, output and exit status from the
publication preparation. Private workspace/interpreter prefixes are redacted as
`<publication>` and `<isolated-python>`; `ruff` denotes the repository-pinned
0.16.6 executable. No output has been replaced with expected results.

- `integration.json`: 733 selected tests passed (290 safeguards + 443 upstream).
- `ruff-check.json` and `ruff-format.json`: whole-checkout lint and formatting.
- `compileall.json`: package, safeguards and included scripts compile.
- `version-check.json`: all 13 version values agree at 3.11.0.
- `shadow-demo.json`: expected synthetic decisions and preserved source hashes.
- `FROZEN_SOURCE.patch`: exact corrected source/tests/scripts/CI diff relative
  to the v3.11.0 release base, including both formerly untracked regression files.

The publication manifest records the freeze digest and all 21 source fingerprints.
The old rejected freeze and verdict remain historical. These checks are selected
local validation, not a full upstream or independent final-patch/Claude approval.
See [the correction record](../THIRD_CORRECTION.md) for scope and remaining
deployment blockers.
