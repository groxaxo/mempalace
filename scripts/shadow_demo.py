"""Generate disposable synthetic audit inputs and run the real shadow CLI."""

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    directory = root / "test-tmp" / "shadow-demo"
    directory.mkdir(parents=True, exist_ok=True)
    sentinel = "SYNTHETIC_OPAQUE_DO_NOT_INDEX"
    fragments = json.dumps(
        {"type": "response_item", "payload": {"type": "reasoning", "encrypted_content": sentinel}}
    )
    canonical = (
        "\n".join(
            json.dumps(event)
            for event in [
                {"type": "session_meta"},
                {
                    "type": "event_msg",
                    "payload": {"type": "user_message", "message": "Tokyo uses JST."},
                },
                {
                    "type": "event_msg",
                    "payload": {"type": "agent_message", "message": "JST is UTC+9."},
                },
            ]
        )
        + "\n"
        + fragments
    )
    samples = {
        "facts.json": json.dumps({"retries": 3, "fact": "Tokyo uses JST", "bytes": [1, 2, 3]}),
        "canonical.jsonl": canonical,
        "headerless.jsonl": fragments,
        "encoded.json": json.dumps(canonical),
        "excess-encoding.json": json.dumps(json.dumps(canonical)),
        "command-output.txt": "ERROR: missing synthetic dependency\n"
        + base64.b64encode(bytes(range(256)) * 12).decode(),
    }
    paths = []
    for name, content in samples.items():
        path = directory / name
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    command = [sys.executable, "-m", "mempalace.ingestion_audit", *(str(path) for path in paths)]
    result = subprocess.run(command, cwd=root, env=dict(os.environ, TMPDIR=str(root / "test-tmp")))
    assert before == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
