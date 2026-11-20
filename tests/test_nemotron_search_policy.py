import re
from unittest.mock import Mock

import pytest

import mempalace.searcher as searcher


class RankedDrawers:
    metadata = {"hnsw:space": "cosine"}

    def query(self, **kwargs):
        rows = list(range(8))[: kwargs["n_results"]]
        return {
            "ids": [[f"drawer-{index}" for index in rows]],
            "documents": [[f"Distinct fixture passage {index}." for index in rows]],
            "metadatas": [[{"source_file": f"source-{index}.md"} for index in rows]],
            "distances": [[index / 10 for index in rows]],
        }


def unexpected(*args, **kwargs):
    raise AssertionError("Nemotron search used lexical scoring, closet boosts or lexical fallback")


@pytest.mark.parametrize("profile", ["nemotron-vllm", "openai-compat"])
@pytest.mark.parametrize("requested,expected", [(100, 5), (2, 2), (-1, 0)])
def test_nemotron_search_caps_and_keeps_vector_order(monkeypatch, profile, requested, expected):
    monkeypatch.setenv("MEMPALACE_EMBEDDING_MODEL", profile)
    monkeypatch.setenv("MEMPALACE_EMBEDDING_API_MODEL", "nemotron-embed")
    monkeypatch.setattr(
        searcher, "_open_search_collection", lambda *a, **kw: (RankedDrawers(), None)
    )
    monkeypatch.setitem(searcher._CANDIDATE_MERGERS, "union", unexpected)
    monkeypatch.setattr(searcher, "_hybrid_rank", unexpected)
    closets = Mock(side_effect=unexpected)
    monkeypatch.setattr(searcher, "get_closets_collection", closets)
    result = searcher.search_memories(
        "remember fixture", "/unused-palace", n_results=requested, candidate_strategy="union"
    )
    assert [hit["drawer_id"] for hit in result["results"]] == [
        f"drawer-{index}" for index in range(expected)
    ]
    closets.assert_not_called()


@pytest.mark.parametrize("requested,expected", [(50, 5), (2, 2), (-1, 0)])
def test_nemotron_cli_search_caps_matching_rows(monkeypatch, capsys, requested, expected):
    monkeypatch.setenv("MEMPALACE_EMBEDDING_MODEL", "nemotron-vllm")
    monkeypatch.setattr(searcher, "_hybrid_rank", unexpected)
    searcher.search(
        "remember fixture", "/unused-palace", n_results=requested, collection=RankedDrawers()
    )
    output = capsys.readouterr().out
    assert len(re.findall(r"^  \[\d+\]", output, re.MULTILINE)) == expected
    assert "bm25=" not in output


def test_nemotron_refuses_automatic_lexical_fallback(monkeypatch):
    monkeypatch.setenv("MEMPALACE_EMBEDDING_MODEL", "nemotron-vllm")
    monkeypatch.setattr(searcher, "_vector_disabled_with_window", unexpected)
    result = searcher.search_memories("remember fixture", "/unused-palace", vector_disabled=True)
    assert result["results"] == []
    assert "requires a working vector index" in result["error"]
