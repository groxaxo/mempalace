"""Second review controls: synthetic source only, with bounded malicious probes."""

import ast
import json
import subprocess
import sys
import textwrap

import pytest

from mempalace import miner
from mempalace.ingestion import _LITERAL_TOKENS, _complete_source_literal, admit_text
from mempalace.normalize import _format_tool_result, normalize, normalize_conversations
from test_writers import writer_spies as writer_spies


TRANSPORT_LITERAL = '{"rawOutput":{"base64":0}}'
UNTERMINATED_LEXEMES = [
    pytest.param("/*a" * 64, id="repeated-block-starts"),
    pytest.param("/*/", id="overlapping-block-delimiters"),
    pytest.param('"' + r"a\"/*" * 64, id="escaped-double-quotes"),
    pytest.param("'" + r"a\'/*" * 64, id="escaped-single-quotes"),
    pytest.param('"unclosed\\', id="double-trailing-backslash"),
    pytest.param("'unclosed\\", id="single-trailing-backslash"),
]


@pytest.mark.parametrize("tail", UNTERMINATED_LEXEMES)
def test_unterminated_lexeme_consumes_one_terminal_token(tail):
    source = TRANSPORT_LITERAL + tail
    tokens = _LITERAL_TOKENS.findall(source)
    assert "".join(tokens) == source
    assert tokens[-1] == tail, "An unterminated lexeme must not retry on its inner starts"
    assert tokens == _LITERAL_TOKENS.findall(TRANSPORT_LITERAL) + [tail]


@pytest.mark.parametrize("tail", UNTERMINATED_LEXEMES)
def test_unterminated_lexemes_refuse_typed_transport(tail):
    source = TRANSPORT_LITERAL + tail
    assert not _complete_source_literal(source)
    admission = admit_text(source, spellcheck=False)
    assert not admission.indexable and admission.text == ""
    assert admission.omissions == {"malformed_transport": 1}


@pytest.mark.parametrize("repetitions", [32, 128, 512])
def test_repeated_block_starts_stay_one_lexeme_at_each_size(repetitions):
    comment = "/*a" * repetitions
    assert _LITERAL_TOKENS.findall(comment) == [comment]
    assert _LITERAL_TOKENS.findall(comment + "*/") == [comment + "*/"]
    assert not _complete_source_literal(TRANSPORT_LITERAL + comment)
    assert _complete_source_literal(TRANSPORT_LITERAL + comment + "*/")


@pytest.mark.parametrize(
    "source",
    [
        TRANSPORT_LITERAL + "/**/",
        TRANSPORT_LITERAL + "/* multiple /* inner starts /* are comment text */;",
        TRANSPORT_LITERAL + '// a complete line comment with /* and "\n',
        '[{"rawOutput":{"base64":\'literal \\\' /* and # text\'}}, # comment\n]',
    ],
)
def test_complete_comments_and_quoted_delimiters_keep_source(source):
    assert _complete_source_literal(source)
    admission = admit_text(source, spellcheck=False)
    assert admission.decision == "keep" and admission.indexable
    assert admission.text == source and admission.omissions == {}


@pytest.mark.skipif(sys.platform != "linux", reason="Probe requires Linux resource limits")
def test_repeated_unterminated_comment_repro_has_finite_resource_budget():
    probe = textwrap.dedent(
        """\
        import json
        import resource
        import signal
        import socket
        import time

        resource.setrlimit(resource.RLIMIT_CPU, (3, 4))
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2, 256 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        signal.alarm(6)

        def forbidden(*args, **kwargs):
            raise AssertionError("Network boundary reached in synthetic probe")

        socket.socket.connect = socket.socket.connect_ex = forbidden
        socket.getaddrinfo = socket.create_connection = forbidden

        from mempalace.ingestion import admit_text

        source = '{"rawOutput":{"base64":0}}' + '/*a' * 12000
        started = time.monotonic()
        result = admit_text(source, spellcheck=False)
        print(json.dumps({"source_bytes": len(source),
                          "elapsed_seconds": time.monotonic() - started,
                          "decision": result.decision,
                          "omissions": result.omissions}), flush=True)
        assert not result.indexable and result.text == ""
        assert result.omissions == {"malformed_transport": 1}
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )
    print(
        json.dumps(
            {
                "probe_command": [sys.executable, "-c", probe],
                "exit_status": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "limits": {
                    "cpu_soft_seconds": 3,
                    "cpu_hard_seconds": 4,
                    "address_space_bytes": 256 * 1024**2,
                    "alarm_seconds": 6,
                    "parent_timeout_seconds": 8,
                },
            }
        )
    )
    assert completed.returncode == 0, "Bounded comment probe exhausted its resource budget"


EXACT_TRIPLE_SOURCE = '[{"rawOutput": {"base64": """example " # literal"""}},]'
_TRIPLE_BODY = "example \" and ' # literal\n/* start // literal \\n"
PYTHON_TRIPLE_SOURCES = [pytest.param(EXACT_TRIPLE_SOURCE, id="exact-review-repro")] + [
    pytest.param(
        '[{"rawOutput": {"base64": ' + prefix + delimiter + _TRIPLE_BODY + delimiter + "}},]",
        id=label,
    )
    for label, prefix, delimiter in [
        ("single", "", "'''"),
        ("raw-double", "r", '"""'),
        ("raw-uppercase-single", "R", "'''"),
        ("unicode-double", "u", '"""'),
        ("bytes-single", "b", "'''"),
        ("bytes-raw-double", "br", '"""'),
        ("raw-bytes-single", "rb", "'''"),
        ("uppercase-bytes-raw-double", "BR", '"""'),
    ]
]


@pytest.mark.parametrize("source", PYTHON_TRIPLE_SOURCES)
def test_valid_python_triple_literals_remain_verbatim(tmp_path, source):
    assert isinstance(ast.literal_eval(source), list)
    assert _complete_source_literal(source), "Valid Python strings must stay whole"
    admission = admit_text(source, spellcheck=False)
    assert admission.decision == "keep" and admission.indexable
    assert admission.text == source and admission.omissions == {}
    path = tmp_path / "example.py"
    path.write_text(source, encoding="utf-8")
    assert normalize(str(path)) == source
    assert normalize_conversations(str(path)) == [source]
    assert _format_tool_result(source, "Unknown") == "→ " + source


@pytest.mark.parametrize("source", PYTHON_TRIPLE_SOURCES)
def test_project_writer_preserves_python_triple_literals(tmp_path, writer_spies, source):
    collection, storage, embedded = writer_spies
    path = tmp_path / "example.py"
    path.write_text(source, encoding="utf-8")
    result = miner.process_file(
        path, tmp_path, collection, "synthetic", [], "test", False, min_chunk_size=1
    )
    assert result[0] > 0 and result[2] is None
    assert embedded == [source]
    assert storage.writes[0]["documents"] == [source]
    metadata = storage.writes[0]["metadatas"][0]
    assert metadata["ingestion_decision"] == "keep"
    assert json.loads(metadata["ingestion_omissions"]) == {}


INVALID_PYTHON_LITERALS = [
    pytest.param('"""example " # unterminated', id="open-double-triple"),
    pytest.param("'''example ' # unterminated", id="open-single-triple"),
    pytest.param('ur"""example " # invalid prefix"""', id="invalid-prefix"),
    pytest.param('b"""non-ascii 界 # bytes"""', id="invalid-bytes"),
    pytest.param('f"""example " # {review_probe()}"""', id="f-string-call"),
    pytest.param("review_probe()", id="call-expression"),
] + [
    pytest.param(number, id="invalid-number-" + number)
    for number in ("1__0", "1_", "0x__1", "0b1__0", "1_.0", "1e_2")
]


@pytest.mark.parametrize("value", INVALID_PYTHON_LITERALS)
def test_invalid_python_or_executable_expressions_cannot_bypass_refusal(monkeypatch, value):
    import builtins

    def forbidden():
        pytest.fail("Source was executed instead of parsed as a literal")

    monkeypatch.setattr(builtins, "review_probe", forbidden, raising=False)
    source = '[{"rawOutput": {"base64": ' + value + "}},]"
    with pytest.raises((ValueError, SyntaxError)):
        ast.literal_eval(source)
    assert not _complete_source_literal(source)
    admission = admit_text(source, spellcheck=False)
    assert not admission.indexable and admission.text == ""
    assert admission.omissions == {"malformed_transport": 1}
    assert _format_tool_result(source, "Unknown") == ""


@pytest.mark.parametrize(
    "source",
    [
        '{"type":"response_item","payload":{"type":"reasoning",'
        '"encrypted_content":"""example " # literal"""}}',
        '{"messages":[{"role":"user","content":"""example " # literal"""}]}',
        '{"type":"user","message":{"content":"""example " # literal"""}}',
    ],
    ids=["codex", "messages", "claude-code"],
)
def test_valid_python_syntax_does_not_override_supported_envelope_refusal(
    tmp_path, writer_spies, source
):
    assert isinstance(ast.literal_eval(source), dict)
    admission = admit_text(source, spellcheck=False)
    assert not admission.indexable and admission.text == ""
    path = tmp_path / "session.py"
    path.write_text(source, encoding="utf-8")
    with pytest.raises(ValueError):
        normalize_conversations(str(path))
    collection, storage, embedded = writer_spies
    before = dict(storage.rows)
    result = miner.process_file(
        path, tmp_path, collection, "synthetic", [], "test", False, min_chunk_size=1
    )
    assert result[0] == 0 and result[2] == "admission_rejected"
    assert storage.rows == before
    assert storage.writes == storage.deletes == embedded == []
