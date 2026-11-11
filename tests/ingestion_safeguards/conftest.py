"""Synthetic, offline tests: no palace, discovery, or model initialization."""

import socket

import pytest


@pytest.fixture(autouse=True)
def offline_boundaries(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network/service/model boundary reached by an offline test")

    monkeypatch.setattr(socket, "connect", forbidden, raising=False)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    import mempalace.embedding as embedding
    import mempalace.server_registry as registry
    import mempalace.spellcheck as spellcheck

    monkeypatch.setattr(embedding, "configured_embedding_function", forbidden)
    monkeypatch.setattr(registry, "read_live_serverinfo", forbidden)
    monkeypatch.setattr(spellcheck, "spellcheck_user_text", lambda text: text)
