"""Regressions for the third review; synthetic data and bounded subprocesses only."""

import json
import base64
import subprocess
import sys
import textwrap

import pytest

from mempalace.ingestion import NonIndexableContentError, _complete_source_literal, admit_text
from mempalace import miner
from mempalace.normalize import _format_tool_result, normalize, normalize_conversations
from test_writers import writer_spies as writer_spies


@pytest.mark.parametrize("dialect", ["python", "javascript", "json", "encoded", "floor-division"])
@pytest.mark.skipif(sys.platform != "linux", reason="Probe requires Linux resource limits")
def test_flat_container_allocation_is_refused_within_finite_resources(dialect):
    probe = textwrap.dedent(
        """\
        import json
        import resource
        import signal
        import socket
        import sys

        resource.setrlimit(resource.RLIMIT_CPU, (3, 4))
        resource.setrlimit(resource.RLIMIT_AS, (128 * 1024**2, 128 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        signal.alarm(6)

        def forbidden(*args, **kwargs):
            raise AssertionError("Network reached by allocation probe")

        socket.socket.connect = socket.socket.connect_ex = forbidden
        socket.getaddrinfo = socket.create_connection = forbidden
        from mempalace.ingestion import admit_text
        from mempalace.normalize import _format_tool_result

        dialect = sys.argv[1]
        source = '[{"rawOutput":{"base64":0}},' + '0,' * 120000
        source += '0]' if dialect in ('json', 'encoded') else ']'
        if dialect == 'floor-division':
            source = '[{"rawOutput":{"base64":0}},0//1,' + '0,' * 120000 + ']'
        if dialect == 'javascript':
            source += ';'
        if dialect == 'encoded':
            source = json.dumps(source)
        result = admit_text(source, spellcheck=False)
        assert not result.indexable
        if dialect == 'floor-division':
            assert result.omissions == {'malformed_transport': 1}
            assert 'structure_allocation_budget' not in result.reasons
        else:
            assert result.decision == 'unsupported'
            assert result.reasons == ('structure_token_budget',)
        if dialect != 'encoded':
            assert _format_tool_result(source, 'Unknown') == ''
        print(json.dumps({'decision': result.decision, 'reasons': result.reasons,
                          'source_bytes': len(source),
                          'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe, dialect],
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )
    assert completed.returncode == 0, (completed.stdout, completed.stderr, completed.returncode)
    print(completed.stdout)


@pytest.mark.parametrize("suffix", ["]", "];"])
def test_literal_probe_checks_structure_before_constructing_ast(monkeypatch, suffix):
    import mempalace.ingestion as ingestion

    def forbidden(*args, **kwargs):
        pytest.fail("AST allocated before the structure budget")

    monkeypatch.setattr(ingestion.ast, "literal_eval", forbidden)
    source = '[{"rawOutput":{"base64":0}},' + "0," * 20000 + suffix
    with pytest.raises(NonIndexableContentError, match="structure_token_budget") as error:
        _complete_source_literal(source)
    assert error.value.decision == "unsupported"


TRUNCATED_TRANSCRIPTS = [
    '{"role":"assistant","content":',
    '[{"role":"assistant","content":',
    '{"mapping":{"one":{"message":{"author":{"role":"user"},"content":',
    '[{"type":"message","user":"U1","text":',
    '{"messages":[{"role":"assistant","content":',
    '{"chat_messages":[{"sender":"human","text":',
    '{"contents":[{"role":"model","parts":',
    '{"history":[{"role":"user","content":',
    '{"type":"response_item","payload":',
    '{"type":"session_metadata","content":',
    '{"type":"session","version":',
    '{"type":"assistant","padding":"' + "x" * 2100 + '","message":',
    '{"padding":"' + "x" * 8200 + '","type":"session","version":',
    '[{"padding":"' + "x" * 2100 + '","role":"assistant","text":',
    r'{"\u0072ole":"assistant","content":',
    '{"type":"response_item","type":',
    '{"messages":[{"role":"assistant","content":"text"}],"messages":',
    '{"role":"assistant","content":"secret","role":',
    '{"type":"response_item","type":{"unfinished":',
    '{"type":"response_item","type":null,',
]


@pytest.mark.parametrize("source", TRUNCATED_TRANSCRIPTS)
def test_truncated_envelope_families_refuse_without_raw_fallback(tmp_path, writer_spies, source):
    admission = admit_text(source, spellcheck=False)
    assert not admission.indexable and admission.text == ""
    assert admission.decision in ("archive-only", "unsupported")
    path = tmp_path / "incomplete.txt"
    path.write_text(source, encoding="utf-8")
    for normalizer in (normalize, normalize_conversations):
        with pytest.raises(NonIndexableContentError):
            normalizer(str(path))
    collection, storage, embedded = writer_spies
    before = dict(storage.rows)
    result = miner.process_file(
        path, tmp_path, collection, "synthetic", [], "test", False, min_chunk_size=1
    )
    assert result[0] == 0 and result[2] == "admission_rejected"
    assert storage.rows == before and storage.writes == storage.deletes == embedded == []


_EVENT_LINES = "\n".join(
    json.dumps({"type": kind, "message": {"content": text}})
    for kind, text in (("user", "Literal question"), ("assistant", "Literal answer"))
)
COMMENT_AND_STRING_SOURCES = [
    '[ # {"type":"response_item"}\n {"rawOutput":{"base64":0}}]',
    '[{"rawOutput":{"base64":"""example\n{"type":"response_item"}\nexample"""}}]',
    '[/* {"type":"response_item"} */ {"rawOutput":{"base64":0}}];',
    '[/*\n{"type":"response_item"}\n*/ {"rawOutput":{"base64":0}}];',
    '[{"rawOutput":{"base64":"""\n' + _EVENT_LINES + '\n"""}}]',
    "[/*\n" + _EVENT_LINES + '\n*/ {"rawOutput":{"base64":0}}];',
    '{"example":{"type":"response_item"},"messages":["start","stop"]}',
    '{"role":"option","example":{"content":"configuration"}}',
    '{"mapping":{"one":{"message":{"content":"configuration"}}}}',
    '[ # {"role":"assistant","content":\n {"rawOutput":{"base64":0}}]',
]


@pytest.mark.parametrize("source", COMMENT_AND_STRING_SOURCES)
def test_comments_strings_and_nested_configuration_cannot_supply_envelope_fields(
    tmp_path, writer_spies, source
):
    admission = admit_text(source, spellcheck=False)
    assert admission.indexable and admission.decision == "keep"
    assert admission.text == source and admission.omissions == {}
    path = tmp_path / "literal.py"
    path.write_text(source, encoding="utf-8")
    assert normalize(str(path)) == source
    assert normalize_conversations(str(path)) == [source]
    collection, storage, embedded = writer_spies
    result = miner.process_file(
        path, tmp_path, collection, "synthetic", [], "test", False, min_chunk_size=1
    )
    assert result[0] > 0 and result[2] is None
    assert embedded == [source] and storage.writes[0]["documents"] == [source]
    assert storage.writes[0]["metadatas"][0]["ingestion_decision"] == "keep"


JAVASCRIPT_SOURCES = [
    '[{"rawOutput":{"base64":0}, 日本語:"useful"}];',
    '[{"rawOutput":{"base64":0}, café:"useful"}];',
    '[{"rawOutput":{"base64":0}, e\u0301:"useful"}];',
    '[{"rawOutput":{"base64":0}, $日本語:"useful"}];',
    r'[{"rawOutput":{"base64":0}, \u65e5\u672c\u8a9e:"useful"}];',
    '[{"rawOutput":{"base64":0}, ゛x:"useful"}];',
    '[{"rawOutput":{"base64":`documented literal`}}];',
    '[{"rawOutput":{"base64":`escaped \\` and \\\\ text`}}];',
    '[{"rawOutput":{"base64":`line one\n{"type":"response_item"}\nline three`}}];',
    '[{"rawOutput":{"base64":`value ${name}`}}];',
    '[{"rawOutput":{"base64":`${({type:"response_item"})}`}}];',
    '[{"rawOutput":{"base64":`nested ${`inner ${name}`} end`}}];',
    '[{"rawOutput":{"base64":`${/`/.test("x")}`}}];',
    '[{"rawOutput":{"base64":`${/[}`]/.source} ${8 / 2}`}}];',
]


@pytest.mark.parametrize("source", JAVASCRIPT_SOURCES)
def test_unicode_identifiers_and_templates_preserve_admission_formatting_and_writes(
    tmp_path, writer_spies, source
):
    assert _complete_source_literal(source)
    admission = admit_text(source, spellcheck=False)
    assert admission.decision == "keep" and admission.text == source
    assert admission.indexable and admission.omissions == {}
    assert _format_tool_result(source, "Unknown") == "→ " + source
    path = tmp_path / "literal.js"
    path.write_text(source, encoding="utf-8")
    assert normalize(str(path)) == source
    assert normalize_conversations(str(path)) == [source]
    collection, storage, embedded = writer_spies
    result = miner.process_file(
        path, tmp_path, collection, "synthetic", [], "test", False, min_chunk_size=1
    )
    assert result[0] > 0 and result[2] is None
    assert embedded == [source] and storage.writes[0]["documents"] == [source]
    metadata = storage.writes[0]["metadatas"][0]
    assert metadata["ingestion_decision"] == "keep"
    assert json.loads(metadata["ingestion_omissions"]) == {}


_BLOB = base64.b64encode(bytes(range(256)) * 12).decode("ascii")
FENCED_SOURCES = [
    "````markdown\n```text\n" + _BLOB + "\n```\n````",
    "```text\n~~~\n" + _BLOB + "\n```",
    "~~~~markdown\n~~~text\n" + _BLOB + "\n~~~\n~~~~",
    "~~~text\n```\n" + _BLOB + "\n~~~",
    "   ````markdown\n```\n" + _BLOB + "\n   ````  ",
    "```text\n```not a closer\n" + _BLOB + "\n```",
]


@pytest.mark.parametrize("source", FENCED_SOURCES)
def test_fence_delimiter_length_and_closing_syntax_preserve_literal_content(
    tmp_path, writer_spies, source
):
    result = admit_text(source, spellcheck=False)
    assert result.decision == "keep" and result.text == source and result.omissions == {}
    path = tmp_path / "literal.md"
    path.write_text(source, encoding="utf-8")
    assert normalize(str(path)) == source
    collection, storage, embedded = writer_spies
    result = miner.process_file(
        path,
        tmp_path,
        collection,
        "synthetic",
        [],
        "test",
        False,
        chunk_size=len(source) + 100,
        min_chunk_size=1,
    )
    assert result[0] > 0 and result[2] is None
    documents = [doc for write in storage.writes for doc in write["documents"]]
    assert embedded == documents and _BLOB in "\n".join(documents)


@pytest.mark.parametrize("closing", ["```", "`````  "])
def test_matching_fence_closes_before_real_opaque_line(closing):
    source = "```text\nLiteral code\n" + closing + "\n" + _BLOB + "\nUseful result"
    result = admit_text(source, spellcheck=False)
    assert result.decision == "sanitize" and result.indexable
    assert _BLOB not in result.text and "Useful result" in result.text
    assert result.omissions == {"opaque_line": 1}


@pytest.mark.parametrize(
    "messages",
    [
        [
            {"type": "message", "username": "alice", "text": "Question"},
            {"type": "message", "username": "bob", "text": "Answer"},
        ],
        [
            {"role": None, "sender": "human", "text": "Question"},
            {"role": None, "sender": "assistant", "text": "Answer"},
        ],
    ],
)
def test_existing_message_aliases_still_normalize(messages):
    admission = admit_text(json.dumps(messages), spellcheck=False)
    assert admission.decision == "sanitize" and admission.indexable
    assert "normalized_transcript" in admission.reasons
    assert "Question" in admission.text and "Answer" in admission.text
    assert admission.text.lstrip().startswith("> ")
