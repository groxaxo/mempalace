from contextlib import nullcontext

import pytest

from mempalace import convo_miner, miner
from mempalace.backends.embedding_wrapper import EmbeddingCollection
from test_ingestion import (
    OPAQUE,
    canonical_codex,
    claude_tool_transcript,
    codex_fragments,
    opaque_line,
)


class StorageSpy:
    upsert_merges_metadata = False

    def __init__(self):
        self.rows = {"old": ("Valuable old synthetic fact", {"source_file": "old-source"})}
        self.writes = []
        self.deletes = []

    def get(self, **kwargs):
        keys = [key for key in kwargs.get("ids", []) if key in self.rows]
        return {
            "ids": keys,
            "documents": [self.rows[key][0] for key in keys],
            "metadatas": [self.rows[key][1] for key in keys],
        }

    def delete(self, **kwargs):
        self.deletes.append(kwargs)
        if kwargs.get("ids") is not None:
            for key in kwargs["ids"]:
                self.rows.pop(key, None)
        else:
            for key, (_, meta) in list(self.rows.items()):
                if all(meta.get(field) == value for field, value in kwargs["where"].items()):
                    del self.rows[key]

    def upsert(self, **kwargs):
        assert (
            len(kwargs["ids"])
            == len(kwargs["documents"])
            == len(kwargs["metadatas"])
            == len(kwargs["embeddings"])
        )
        self.writes.append(kwargs)
        for key, doc, meta in zip(kwargs["ids"], kwargs["documents"], kwargs["metadatas"]):
            self.rows[key] = (doc, meta)

    add = upsert


@pytest.fixture
def writer_spies(monkeypatch):
    import mempalace.backends.embedding_wrapper as wrapper

    storage, embedded = StorageSpy(), []

    def embed(texts, **kwargs):
        embedded.extend(texts)
        return [[float(len(text)), 0.0] for text in texts]

    monkeypatch.setattr(wrapper, "_resolve_document_embedder", lambda: object())
    monkeypatch.setattr(wrapper, "_embed_texts", embed)
    for module in (convo_miner, miner):
        monkeypatch.setattr(module, "mine_lock", lambda *args: nullcontext())
        monkeypatch.setattr(module, "file_already_mined", lambda *args, **kwargs: False)
    monkeypatch.setattr(convo_miner, "_detect_hall_cached", lambda text: "general")
    monkeypatch.setattr(convo_miner, "entities_metadata", lambda text: "")
    monkeypatch.setattr(miner, "detect_hall", lambda text: "general")
    monkeypatch.setattr(miner, "_extract_entities_for_metadata", lambda text: "")
    monkeypatch.setattr(convo_miner, "_source_file_delete_ids", lambda *args: ["old"])
    return EmbeddingCollection(storage), storage, embedded


def test_unsupported_conversation_is_not_registered_as_refreshed(tmp_path, writer_spies):
    collection, storage, embedded = writer_spies
    source = tmp_path / "unsupported.jsonl"
    source.write_text('{"messages":[{"role":"assistant","content":')
    assert (
        convo_miner._normalize_convo_conversations(
            source,
            str(source),
            collection,
            "synthetic",
            "test",
            "exchange",
            False,
        )
        is None
    )
    assert storage.writes == [] and embedded == [] and "old" in storage.rows


def test_conversation_chunk_gate_rejects_before_purge(writer_spies):
    collection, storage, embedded = writer_spies
    result = convo_miner._file_chunks_locked(
        collection,
        "synthetic.jsonl",
        [{"content": codex_fragments(), "chunk_index": 0}],
        "synthetic",
        "conversations",
        "test",
        "exchange",
    )
    assert result[0] == 0 and result[2] == "admission_rejected"
    assert storage.deletes == [] and storage.writes == [] and embedded == []
    assert "old" in storage.rows


def test_project_transcript_rejected_before_deletion(tmp_path, writer_spies):
    collection, storage, embedded = writer_spies
    source = tmp_path / "fragment.jsonl"
    source.write_text(codex_fragments())
    result = miner.process_file(
        source, tmp_path, collection, "synthetic", [], "test", False, min_chunk_size=1
    )
    assert result[0] == 0 and result[2] == "admission_rejected"
    assert storage.deletes == [] and storage.writes == [] and embedded == []
    assert "old" in storage.rows


def test_supported_project_transcript_is_selected_before_embedding(tmp_path, writer_spies):
    collection, storage, embedded = writer_spies
    source = tmp_path / "session.jsonl"
    source.write_text(canonical_codex())
    result = miner.process_file(
        source, tmp_path, collection, "synthetic", [], "test", False, min_chunk_size=1
    )
    assert result[0] > 0 and result[2] is None
    assert OPAQUE not in "\n".join(embedded) and "session_meta" not in "\n".join(embedded)
    assert "東京 uses JST" in "\n".join(embedded)
    assert embedded == [doc for write in storage.writes for doc in write["documents"]]
    for write in storage.writes:
        for meta in write["metadatas"]:
            assert meta["source_file"] == str(source)
            assert meta["ingestion_decision"] == "sanitize"
            assert "line_start" not in meta and "line_end" not in meta


def test_project_positive_config_code_and_multilingual_facts(tmp_path, writer_spies):
    collection, storage, embedded = writer_spies
    source = tmp_path / "config.json"
    text = '{"bytes":[1,2,3],"encrypted_content":"documented option","facts":"東京 日本 Aotearoa"}'
    source.write_text(text)
    result = miner.process_file(
        source, tmp_path, collection, "synthetic", [], "test", False, min_chunk_size=1
    )
    assert result[0] > 0 and text in "\n".join(embedded)
    assert storage.writes[0]["metadatas"][0]["line_start"] == 1


@pytest.mark.parametrize("writer", ["live", "manual"])
def test_live_and_manual_drawers_cannot_bypass_admission(writer_spies, writer):
    collection, storage, embedded = writer_spies
    if writer == "live":
        result = convo_miner.file_conversation_exchange(
            collection,
            wing="synthetic",
            room="conversations",
            text=codex_fragments(),
            source_file="synthetic.jsonl",
            agent="test",
        )
    else:
        result = miner.add_drawer(
            collection, "synthetic", "general", codex_fragments(), "synthetic.jsonl", 0, "test"
        )
    assert not result
    assert embedded == [] and storage.writes == [] and storage.deletes == []


def test_live_exchange_retains_facts_source_and_omission_metadata(writer_spies):
    import json

    collection, storage, embedded = writer_spies
    result = convo_miner.file_conversation_exchange(
        collection,
        wing="synthetic",
        room="conversations",
        text=json.dumps(
            {"error": "exit 2: missing header", "rawOutput": {"base64": OPAQUE, "bytes": [77, 88]}}
        ),
        source_file="synthetic.jsonl",
        agent="test",
        extra_metadata={"ingestion_decision": "keep", "source_file": "wrong"},
    )
    assert result and "missing header" in "\n".join(embedded) and OPAQUE not in "\n".join(embedded)
    meta = storage.writes[0]["metadatas"][0]
    assert meta["source_file"] == "synthetic.jsonl" and meta["ingestion_decision"] == "sanitize"
    assert "opaque_transport" in meta["ingestion_omissions"]
    assert "ingestion omitted" not in "\n".join(embedded)


def test_conversation_source_is_admitted_before_opaque_spans_can_be_chunked(tmp_path, writer_spies):
    collection, storage, embedded = writer_spies
    source = tmp_path / "conversation.txt"
    source.write_text(
        "Build diagnosis: missing synthetic dependency.\n\n"
        + opaque_line()
        + "\n\nInstall the synthetic dependency before retrying."
    )
    conversations = convo_miner._normalize_convo_conversations(
        source, str(source), collection, "synthetic", "test", "exchange", False
    )
    assert conversations
    chunks = convo_miner.chunk_exchanges(
        "\n\n".join(conversations), chunk_size=120, min_chunk_size=1
    )
    result = convo_miner._file_chunks_locked(
        collection, str(source), chunks, "synthetic", "conversations", "test", "exchange"
    )
    assert result[0] > 0
    assert opaque_line()[:40] not in "\n".join(embedded)
    assert "missing synthetic dependency" in "\n".join(embedded)
    assert all("ingestion omitted" not in doc for doc in embedded)


def test_admitted_code_examples_are_not_reinterpreted_as_fragment_envelopes(writer_spies):
    from mempalace.ingestion import admit_text

    collection, storage, embedded = writer_spies
    text = (
        'Documented example:\n```json\n{"type":"response_item","payload":{"type":"reasoning"}}\n```'
    )
    admission = admit_text(text)
    # A line-preserving chunker can put the JSON example in its own chunk.
    chunks = [{"content": line, "chunk_index": i} for i, line in enumerate(text.splitlines())]
    result = convo_miner._file_chunks_locked(
        collection,
        "example.md",
        chunks,
        "synthetic",
        "conversations",
        "test",
        "exchange",
        admission_metadata=admission.metadata(),
    )
    assert result[0] == len(chunks)
    assert '"type":"response_item"' in "\n".join(embedded)


def test_conversation_source_provenance_survives_chunking(tmp_path, writer_spies):
    collection, storage, embedded = writer_spies
    source = tmp_path / "claude.jsonl"
    source.write_text(
        claude_tool_transcript(
            '{"stderr":"missing dependency","rawOutput":{"base64":"' + OPAQUE + '"}}'
        )
    )
    metadata = {}
    conversations = convo_miner._normalize_convo_conversations(
        source, str(source), collection, "synthetic", "test", "exchange", False, metadata
    )
    chunks = convo_miner.chunk_exchanges(
        "\n\n".join(conversations), chunk_size=120, min_chunk_size=1
    )
    result = convo_miner._file_chunks_locked(
        collection,
        str(source),
        chunks,
        "synthetic",
        "conversations",
        "test",
        "exchange",
        admission_metadata=metadata,
    )
    assert result[0] > 0 and OPAQUE not in "\n".join(embedded)
    for write in storage.writes:
        for meta in write["metadatas"]:
            assert "opaque_transport" in meta["ingestion_omissions"]
            assert meta["ingestion_decision"] == "sanitize" and meta["source_file"] == str(source)


@pytest.mark.parametrize(
    "chunks",
    [
        [],
        [
            {"content": "A valuable synthetic fact.", "chunk_index": 0},
            {"content": codex_fragments(), "chunk_index": 1},
        ],
    ],
)
def test_empty_or_partially_rejected_replacement_preserves_existing_rows(writer_spies, chunks):
    collection, storage, embedded = writer_spies
    before = dict(storage.rows)
    result = convo_miner._file_chunks_locked(
        collection, "source.jsonl", chunks, "synthetic", "conversations", "test", "exchange"
    )
    assert result[2] == "admission_rejected" and result[0] == 0
    assert storage.rows == before and storage.deletes == [] and embedded == []


def test_project_source_code_hashes_and_multilingual_facts_survive_embedding(
    tmp_path, writer_spies
):
    collection, storage, embedded = writer_spies
    source = tmp_path / "example.py"
    text = 'def encrypted_content():\n    return "東京 uses JST"\n# ID: ' + "a" * 64
    source.write_text(text)
    result = miner.process_file(
        source, tmp_path, collection, "synthetic", [], "test", False, min_chunk_size=1
    )
    assert result[0] > 0 and "\n".join(embedded) == text
