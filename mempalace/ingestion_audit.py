"""Read-only ingestion shadow audit. Never opens a palace or prints content.

Usage: python -m mempalace.ingestion_audit FILE [FILE ...]
Only explicitly supplied regular files are read; no discovery or archival copy.
"""

import argparse
from collections import Counter
import json

from .ingestion import NonIndexableContentError, admit_text, indexing_text
from .normalize import _read_transcript_file


def audit_files(paths) -> dict:
    files = []
    decisions = Counter({key: 0 for key in ("keep", "sanitize", "archive-only", "unsupported")})
    for path in paths:
        source = str(path)
        row = {"source": source}
        try:
            text, fingerprint = _read_transcript_file(source, with_fingerprint=True)
            row.update(fingerprint)
            # Spellcheck can read personal entity/config data. The shadow
            # classifier needs no such dependencies and never imports them.
            result = admit_text(text, source=source, spellcheck=False)
            counts = {reason: result.omissions.get(reason, 1) for reason in result.reasons}
            row.update(
                decision=result.decision,
                reason_counts=counts,
                omission_counts=result.omissions,
                conversations=len(result.conversations),
                selected_bytes=len(indexing_text(result.text).encode("utf-8", errors="replace")),
            )
        except NonIndexableContentError as exc:
            row.update(
                decision=exc.decision,
                reason_counts={exc.reason: 1},
                omission_counts={},
                conversations=0,
                selected_bytes=0,
            )
        except OSError:
            # Errors may include paths or other source-derived strings. Only
            # a fixed code is exposed, never exception text or content previews.
            row.update(
                decision="unsupported",
                reason_counts={"unreadable_source": 1},
                omission_counts={},
                conversations=0,
                selected_bytes=0,
            )
        decisions[row["decision"]] += 1
        files.append(row)
    return {
        "policy_version": 1,
        "mode": "shadow",
        "decision_counts": dict(decisions),
        "files": files,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="Explicit source files (no directories or palace)")
    args = parser.parse_args(argv)
    print(json.dumps(audit_files(args.files), ensure_ascii=True, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
