"""Exercise the real exec-loaded handlers without starting an MCP transport."""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import pytest

from mempalace.config import sanitize_content, sanitize_name, strip_lone_surrogates
from mempalace.ids import ID_RECIPE, make_drawer_id_from_content
from mempalace.source_identity import identity_metadata
from test_ingestion import OPAQUE, codex_fragments
from test_writers import writer_spies as writer_spies  # shared offline fixture


@pytest.fixture
def handlers(writer_spies):
    collection, storage, embedded = writer_spies
    events = []
    namespace = dict(
        __name__="mempalace.mcp_server",
        __package__="mempalace.mcp_server",
        Optional=Optional,
        datetime=datetime,
        hashlib=hashlib,
        json=json,
        logger=logging.getLogger("test"),
        sanitize_content=sanitize_content,
        sanitize_name=sanitize_name,
        strip_lone_surrogates=strip_lone_surrogates,
        ID_RECIPE=ID_RECIPE,
        make_drawer_id_from_content=make_drawer_id_from_content,
        identity_metadata=identity_metadata,
        _config=SimpleNamespace(chunk_size=80),
        _get_collection=lambda **kwargs: collection,
        _safe_meta=dict,
        _wal_log=lambda *args: events.append(args),
        _wal_result=lambda *args: events.append(args),
        _get_result_ids=lambda result: result["ids"],
        _invalidate_overview_caches=lambda: None,
        _embed_failure=lambda exc, **kwargs: {"success": False, "error": str(exc)},
        assert_no_collisions=lambda *args: None,
    )
    root = Path(__file__).resolve().parents[2]
    for fragment in ("tools_write.py", "tools_diary.py"):
        path = root / "mempalace" / "mcp_server" / fragment
        exec(compile(path.read_text(), str(path), "exec"), namespace)
    namespace["_logical_drawer_record"] = lambda *args: {
        "content": "old synthetic fact",
        "metadata": {"source_file": "old-source"},
        "ids": ["old"],
    }
    namespace["_purge_source_closets"] = lambda *args, **kwargs: events.append("purge") or 1
    namespace["tool_check_duplicate"] = lambda content, **kwargs: (
        events.append(("duplicate_embedding", content)) or {"is_duplicate": False}
    )
    return namespace, events


@pytest.mark.parametrize("operation", ["add", "update", "diary", "checkpoint"])
def test_mcp_writers_reject_before_wal_embedding_or_purge(handlers, writer_spies, operation):
    namespace, events = handlers
    _, storage, embedded = writer_spies
    if operation == "add":
        result = namespace["tool_add_drawer"]("synthetic", "facts", codex_fragments())
    elif operation == "update":
        result = namespace["tool_update_drawer"]("old", content=codex_fragments())
    elif operation == "diary":
        result = namespace["tool_diary_write"]("synthetic", codex_fragments())
    else:
        result = namespace["tool_checkpoint"](
            [{"wing": "synthetic", "room": "facts", "content": codex_fragments()}]
        )
    assert not result.get("success", False)
    assert events == [] and embedded == [] and storage.writes == [] and storage.deletes == []
    assert "old" in storage.rows


@pytest.mark.parametrize("operation", ["add", "diary"])
def test_mcp_selected_evidence_and_metadata_remain_aligned(handlers, writer_spies, operation):
    namespace, events = handlers
    _, storage, embedded = writer_spies
    text = json.dumps(
        {"stderr": "ERROR: missing synthetic header", "rawOutput": {"base64": OPAQUE}}
    )
    if operation == "add":
        result = namespace["tool_add_drawer"](
            "synthetic", "facts", text, source_file="synthetic.json"
        )
    else:
        result = namespace["tool_diary_write"]("synthetic", text)
    assert result["success"]
    assert "missing synthetic header" in "".join(embedded) and OPAQUE not in "".join(embedded)
    assert OPAQUE not in repr(events)
    assert all(
        meta["ingestion_decision"] == "sanitize"
        for write in storage.writes
        for meta in write["metadatas"]
    )


def test_sanitized_add_remains_idempotent(handlers, writer_spies):
    namespace, _ = handlers
    _, storage, embedded = writer_spies
    text = '{"stderr":"ERROR: missing dependency","rawOutput":{"base64":"' + OPAQUE + '"}}'
    first = namespace["tool_add_drawer"]("synthetic", "facts", text)
    writes, inputs = len(storage.writes), list(embedded)
    second = namespace["tool_add_drawer"]("synthetic", "facts", text)
    assert first["success"] and second["reason"] == "already_exists"
    assert first["drawer_id"] == second["drawer_id"]
    assert len(storage.writes) == writes and embedded == inputs


def test_update_with_sanitized_content_preserves_row_alignment(handlers, writer_spies):
    namespace, _ = handlers
    _, storage, embedded = writer_spies
    namespace["_config"].chunk_size = 20
    text = '{"stderr":"ERROR: missing dependency","rawOutput":{"base64":"' + OPAQUE + '"}}'
    result = namespace["tool_update_drawer"]("old", content=text)
    assert result["success"] and result["chunks"] > 1
    assert OPAQUE not in "".join(embedded) and "missing dependency" in "".join(embedded)
    assert "old" not in storage.rows and len(storage.rows) == result["chunks"]


def test_metadata_update_of_legacy_opaque_content_requires_explicit_replacement(
    handlers, writer_spies
):
    namespace, events = handlers
    _, storage, embedded = writer_spies
    namespace["_logical_drawer_record"] = lambda *args: {
        "content": codex_fragments(),
        "metadata": {"source_file": "old-source"},
        "ids": ["old"],
    }
    result = namespace["tool_update_drawer"]("old", wing="synthetic")
    assert result == {"success": False, "error": "existing_content_requires_review"}
    assert events == [] and embedded == [] and storage.deletes == [] and "old" in storage.rows
