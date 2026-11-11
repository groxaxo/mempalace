"""Content preservation controls using synthetic input and offline writer spies."""

import json

import pytest

from mempalace import convo_miner, miner
from mempalace.ingestion import admit_text, indexing_text
from mempalace.normalize import _format_tool_result, normalize, normalize_conversations
from test_ingestion import OPAQUE, claude_tool_transcript, opaque_line
from test_writers import writer_spies as writer_spies


MARKER = "[ingestion omitted: opaque_transport; count=1]"
LITERALS = [
    f"Document this exact token: {MARKER}",
    f'```python\nannotation = "{MARKER}"\n```',
    json.dumps({"annotation": MARKER}),
    MARKER,
    f"\ue000 {MARKER} \U000f0000 [ingestion omitted: tool_total_bytes]",
]


@pytest.mark.parametrize("content", LITERALS, ids=["prose", "fenced", "config", "only", "unicode"])
def test_literal_omission_markers_remain_indexable_content(tmp_path, content):
    result = admit_text(content, spellcheck=False)
    assert result.decision == "keep" and result.omissions == {}
    assert indexing_text(result.text) == content
    assert result.indexable
    assert "\n\n".join(result.require_conversations()) == content
    source = tmp_path / "literal.txt"
    source.write_text(content, encoding="utf-8")
    assert normalize(str(source)) == content
    assert normalize_conversations(str(source)) == [content]


def test_identical_literal_and_real_omission_have_separate_provenance():
    source = json.dumps({"message": MARKER, "rawOutput": {"base64": OPAQUE}})
    result = admit_text(source, spellcheck=False)
    assert result.decision == "sanitize" and result.omissions == {"opaque_transport": 1}
    assert json.loads(indexing_text(result.text)) == {"message": MARKER}
    assert result.text.count(MARKER) == 1
    assert json.loads(result.metadata()["ingestion_omissions"]) == {"opaque_transport": 1}


def test_selected_tool_blocks_survive_normalizer_joins_and_merges(tmp_path):
    output = [
        {"type": "text", "text": f"The literal token is {MARKER}"},
        {
            "type": "text",
            "text": json.dumps({"stderr": "Useful failure", "rawOutput": {"base64": OPAQUE}}),
        },
    ]
    source = claude_tool_transcript(output)
    result = admit_text(source, spellcheck=False)
    selected = "\n\n".join(result.require_conversations())
    assert selected.count(MARKER) == 1
    assert "Useful failure" in selected and OPAQUE not in selected
    assert "[ingestion omitted:" not in selected.replace(MARKER, "")
    assert result.omissions["opaque_transport"] == 1
    assert result.omissions["typed_nontext"] == 2
    path = tmp_path / "session.jsonl"
    path.write_text(source, encoding="utf-8")
    displayed = normalize_conversations(str(path))
    assert isinstance(displayed, list) and all(isinstance(item, str) for item in displayed)
    assert MARKER in displayed[0] and "Useful failure" in displayed[0]
    assert "ingestion omitted" in normalize(str(path))


@pytest.mark.parametrize("width", [220, 377, 479])
def test_tool_byte_caps_preserve_retained_literals_without_annotation_fragments(width):
    output = MARKER + "\n" + "\n".join(["証拠 " + "界" * 600] * 7 + ["Evidence " + "x" * width])
    result = admit_text(claude_tool_transcript(output), spellcheck=False)
    selected = indexing_text(result.text)
    assert selected.count(MARKER) == 1
    assert "[ingestion omitted:" not in selected.replace(MARKER, "")
    tool_text = selected[selected.index("→ ") :]
    assert len(tool_text.encode("utf-8")) <= 2048
    assert all(len(line.encode("utf-8")) <= 512 for line in tool_text.splitlines())
    assert "\ufffd" not in selected
    assert result.omissions["tool_line_bytes"] > 0
    assert result.omissions["tool_total_bytes"] > 0


@pytest.mark.parametrize("writer", ["live", "manual", "project"])
@pytest.mark.parametrize("content", LITERALS[:4], ids=["prose", "fenced", "config", "only"])
def test_writers_preserve_literal_documents_and_admission_metadata(
    tmp_path, writer_spies, writer, content
):
    collection, storage, embedded = writer_spies
    source = tmp_path / "example.md"
    source.write_text(content, encoding="utf-8")
    if writer == "live":
        result = convo_miner.file_conversation_exchange(
            collection,
            wing="synthetic",
            room="facts",
            text=content,
            source_file=str(source),
            agent="test",
        )
    elif writer == "manual":
        result = miner.add_drawer(collection, "synthetic", "facts", content, str(source), 0, "test")
    else:
        result = miner.process_file(
            source, tmp_path, collection, "synthetic", [], "test", False, min_chunk_size=1
        )
        assert result[0] > 0 and result[2] is None
    assert result
    assert embedded == [content]
    assert [doc for write in storage.writes for doc in write["documents"]] == [content]
    metadata = storage.writes[0]["metadatas"][0]
    assert metadata["source_file"] == str(source)
    assert metadata["ingestion_decision"] == "keep"
    assert json.loads(metadata["ingestion_omissions"]) == {}


@pytest.mark.parametrize("writer", ["live", "manual", "project", "conversation"])
def test_writers_preserve_mixed_literal_and_omission_metadata(tmp_path, writer_spies, writer):
    collection, storage, embedded = writer_spies
    text = json.dumps({"message": MARKER, "rawOutput": {"base64": OPAQUE}})
    source = tmp_path / "mixed.json"
    source.write_text(text, encoding="utf-8")
    if writer == "live":
        assert convo_miner.file_conversation_exchange(
            collection,
            wing="synthetic",
            room="facts",
            text=text,
            source_file=str(source),
            agent="test",
        )
    elif writer == "manual":
        assert miner.add_drawer(collection, "synthetic", "facts", text, str(source), 0, "test")
    elif writer == "project":
        result = miner.process_file(
            source, tmp_path, collection, "synthetic", [], "test", False, min_chunk_size=1
        )
        assert result[0] > 0 and result[2] is None
    else:
        metadata = {}
        conversations = convo_miner._normalize_convo_conversations(
            source, str(source), collection, "synthetic", "test", "exchange", False, metadata
        )
        assert conversations
        chunks = convo_miner.chunk_exchanges(
            "\n\n".join(conversations), chunk_size=120, min_chunk_size=1
        )
        result = convo_miner._file_chunks_locked(
            collection,
            str(source),
            chunks,
            "synthetic",
            "facts",
            "test",
            "exchange",
            admission_metadata=metadata,
        )
        assert result[0] > 0 and result[2] is False
    documents = [doc for write in storage.writes for doc in write["documents"]]
    assert embedded == documents == [json.dumps({"message": MARKER}, separators=(",", ":"))]
    assert OPAQUE not in "\n".join(documents)
    for write in storage.writes:
        for metadata in write["metadatas"]:
            assert metadata["source_file"] == str(source)
            assert metadata["ingestion_decision"] == "sanitize"
            assert json.loads(metadata["ingestion_omissions"]) == {"opaque_transport": 1}


SOURCE_LITERALS = [
    '[{"type":"thinking","thinking":\'documented fixture\',"enabled":true,"optional":null}];',
    '[{"type":"thinking",thinking:\'documented fixture\',enabled:true,optional:null,}];',
    '[\n {"rawOutput": "documented API field"}\n];',
    '[\n {"type": "thinking", "thinking": "documented fixture"}\n];',
    '[\n {"rawOutput": "documented API field",},\n]',
    '[\n // rawOutput is an API field\n {"rawOutput": "documented // literal"},\n];',
    '[\n {"type": "thinking", /* documented */ "thinking": "fixture"},\n];',
    '[\n {"rawOutput": "documented API field", "enabled": True},\n]',
    '[\n {"type": "thinking", "thinking": \'documented fixture\'},\n]',
    '[\n {"rawOutput": {"base64": "documented option", "bytes": [1, 2]}},\n];',
    '[\n {"rawOutput": {"base64": "documented option"}}, # Python comment\n]',
    '[\n {"rawOutput": "literal /* comment */ and # text; ,]"},\n];',
    '[\n {"names": ["rawOutput", "thinking", "bytes"], "enabled": False},\n]',
    '```javascript\n[\n {"type": "thinking", "thinking": "documented fixture"}\n];\n```',
]


@pytest.mark.parametrize("content", SOURCE_LITERALS)
def test_source_literals_with_transport_field_names_are_preserved(tmp_path, content):
    result = admit_text(content, spellcheck=False)
    assert result.decision == "keep" and result.indexable
    assert result.text == content and result.omissions == {}
    source = tmp_path / "example.js"
    source.write_text(content, encoding="utf-8")
    assert normalize_conversations(str(source)) == [content]
    assert normalize(str(source)) == content
    assert _format_tool_result(content, "Unknown") == "→ " + content


@pytest.mark.parametrize("content", SOURCE_LITERALS)
def test_project_writer_preserves_source_literals_with_transport_names(
    tmp_path, writer_spies, content
):
    collection, storage, embedded = writer_spies
    source = tmp_path / "example.js"
    source.write_text(content, encoding="utf-8")
    result = miner.process_file(
        source, tmp_path, collection, "synthetic", [], "test", False, min_chunk_size=1
    )
    assert result[0] > 0 and result[2] is None
    assert embedded == [content]
    assert storage.writes[0]["documents"] == [content]
    metadata = storage.writes[0]["metadatas"][0]
    assert metadata["source_file"] == str(source)
    assert metadata["line_start"] == 1
    assert metadata["ingestion_decision"] == "keep"
    assert json.loads(metadata["ingestion_omissions"]) == {}


MALFORMED_TRANSPORT = [
    '{"rawOutput":{"bytes":[91 92]}}',
    '{"rawOutput":{"base64":"' + OPAQUE,
    '{"rawOutput":{"format":"binary","bytes":[91,92',
    '{"rawOutput":[91,92',
    '{"rawOutput":{"bytes":[91,,92]}}',
    '{"rawOutput":"' + opaque_line(),
    '{"type":"Buffer","data":[91,92',
    '{"encoding":"base64","data":"' + OPAQUE,
    '{"type":"thinking","thinking":"' + OPAQUE,
    '{"type":"input_image","source":{"data":"' + OPAQUE,
]


@pytest.mark.parametrize("content", MALFORMED_TRANSPORT)
def test_malformed_typed_transport_remains_nonindexable(content):
    result = admit_text(content, spellcheck=False)
    assert not result.indexable and not result.text
    assert result.omissions["malformed_transport"] == 1
    assert _format_tool_result(content, "Unknown") == ""


@pytest.mark.parametrize("content", MALFORMED_TRANSPORT)
def test_project_writer_refuses_malformed_transport_before_mutation(
    tmp_path, writer_spies, content
):
    collection, storage, embedded = writer_spies
    before = dict(storage.rows)
    source = tmp_path / "transport.js"
    source.write_text(content, encoding="utf-8")
    result = miner.process_file(
        source, tmp_path, collection, "synthetic", [], "test", False, min_chunk_size=1
    )
    assert result[0] == 0 and result[2] == "admission_rejected"
    assert storage.rows == before
    assert storage.writes == storage.deletes == embedded == []


INCOMPLETE_TRANSCRIPTS = [
    pytest.param(
        '{"type":"response_item","payload":{"type":"reasoning","encrypted_content":"'
        + OPAQUE
        + '"}}',
        id="codex",
    ),
    pytest.param('{"type":"user","message":{"content":"Only one turn"}}', id="claude-code"),
    pytest.param('{"chat_messages":[{"sender":"human","text":"Only one turn"}]}', id="claude-ai"),
    pytest.param(
        '{"mapping":{"one":{"parent":null,"children":[],"message":{"author":{"role":"user"},"content":{"parts":["Only one turn"]}}}}}',
        id="chatgpt",
    ),
    pytest.param(
        '{"contents":[{"role":"user","parts":[{"text":"Only one turn"}]}]}', id="gemini-json"
    ),
    pytest.param('{"type":"session_metadata","sessionId":"synthetic"}', id="gemini-jsonl"),
    pytest.param('{"type":"session","version":3,"id":"synthetic"}', id="pi"),
    pytest.param('{"history":[{"role":"user","content":"Only one turn"}]}', id="continue"),
    pytest.param('[{"type":"message","user":"U1","text":"Only one turn"}]', id="slack"),
]


@pytest.mark.parametrize("content", INCOMPLETE_TRANSCRIPTS)
@pytest.mark.parametrize("broken_tail", ["", '\n{"unfinished":'])
def test_supported_incomplete_transcript_families_still_refuse_raw_fallback(
    tmp_path, writer_spies, content, broken_tail
):
    collection, storage, embedded = writer_spies
    text = content + broken_tail
    admission = admit_text(text, spellcheck=False)
    assert not admission.indexable and not admission.text
    source = tmp_path / "session.js"
    source.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        normalize_conversations(str(source))
    result = miner.process_file(
        source, tmp_path, collection, "synthetic", [], "test", False, min_chunk_size=1
    )
    assert result[0] == 0 and result[2] == "admission_rejected"
    assert storage.writes == storage.deletes == embedded == []
    assert "old" in storage.rows
