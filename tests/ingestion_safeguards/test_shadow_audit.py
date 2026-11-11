import hashlib
import json
from pathlib import Path
import subprocess
import sys

from test_ingestion import OPAQUE, canonical_codex, codex_fragments


def test_shadow_cli_classifies_without_palace_imports_or_payload_output(tmp_path):
    samples = {
        "facts.json": '{"bytes":[1,2,3],"fact":"東京 uses JST"}',
        "canonical.jsonl": canonical_codex(),
        "fragment.jsonl": codex_fragments(),
        "unsupported.json": json.dumps(json.dumps(canonical_codex())),
    }
    paths = []
    for name, content in samples.items():
        path = tmp_path / name
        path.write_text(content)
        paths.append(str(path))
    before = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in paths}
    # Running the module is the real public CLI. Fail if it imports storage,
    # configuration, or embedding code, even if no connection was attempted.
    program = (
        "import runpy,sys; sys.argv=['audit']+sys.argv[1:]; "
        "runpy.run_module('mempalace.ingestion_audit',run_name='__main__'); "
        "assert not any(n in sys.modules for n in "
        "['mempalace.palace','mempalace.embedding','mempalace.config','chromadb'])"
    )
    result = subprocess.run([sys.executable, "-c", program, *paths], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert OPAQUE not in result.stdout and "東京" not in result.stdout
    report = json.loads(result.stdout)
    assert report["decision_counts"] == {
        "keep": 1,
        "sanitize": 1,
        "archive-only": 1,
        "unsupported": 1,
    }
    assert {row["source"]: row["sha256"] for row in report["files"]} == before
    assert all(row["reason_counts"] for row in report["files"])
    assert before == {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in paths}


def test_shadow_cli_does_not_follow_symlinks_or_print_read_errors(tmp_path):
    source = tmp_path / "synthetic.txt"
    source.write_text(OPAQUE)
    link = tmp_path / "link.txt"
    link.symlink_to(source)
    result = subprocess.run(
        [sys.executable, "-m", "mempalace.ingestion_audit", str(link)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["files"][0]["decision"] == "unsupported"
    assert report["files"][0]["reason_counts"] == {"unreadable_source": 1}
    assert OPAQUE not in result.stdout + result.stderr
