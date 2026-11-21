import json
import math

import pytest

from mempalace import embedding
from mempalace.config import MempalaceConfig
from mempalace.nemotron_vllm import NemotronVLLMEmbeddingFunction


def test_nemotron_roles_and_token_windows(monkeypatch):
    requests = []

    def post_json(url, body, headers, timeout):
        requests.append((url, body))
        if url.endswith("/tokenize"):
            return {"tokens": list(range(3600))}
        if url.endswith("/detokenize"):
            return {"prompt": f"window {body['tokens'][0]}"}
        return {
            "data": [
                {"index": index, "embedding": [2.0, 0.0] + [0.0] * 2046}
                for index in reversed(range(len(body["input"])))
            ]
        }

    class Response:
        def __init__(self, data):
            self.data = data

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(self.data).encode()

    def urlopen(request, timeout):
        return Response(post_json(request.full_url, json.loads(request.data), {}, timeout))

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    monkeypatch.setattr("mempalace.nemotron_vllm._http_post_json", post_json)
    ef = NemotronVLLMEmbeddingFunction("http://127.0.0.1:8000", "nemotron-embed")
    monkeypatch.setattr(ef, "_verify_model", lambda: None)
    vectors = ef(["short", "旅" * 1600])
    query = ef.embed_query("some query")
    assert requests[3][1]["input"] == [
        "passage: short",
        "passage: window 0",
        "passage: window 3250",
    ]
    assert requests[4][1]["input"] == ["query: some query"]
    assert len(vectors) == 2
    for vector in vectors + query:
        assert len(vector) == 2048
        assert math.hypot(*vector) == pytest.approx(1.0)


@pytest.mark.parametrize("bad", [[1.0] * 384, [0.0] * 2048, [float("nan")] * 2048])
def test_nemotron_refuses_invalid_vectors(bad):
    ef = NemotronVLLMEmbeddingFunction("http://127.0.0.1:8000", "nemotron-embed")
    with pytest.raises(embedding.EmbeddingAPIError, match="wrong-width, zero, or non-finite"):
        ef._vectors_from_response({"data": [{"index": 0, "embedding": bad}]}, 1)


def test_nemotron_persists_existing_identity(monkeypatch):
    monkeypatch.setenv("MEMPALACE_EMBEDDING_MODEL", "openai-compat")
    monkeypatch.setenv("MEMPALACE_EMBEDDING_API_MODEL", "nemotron-embed")
    identity = embedding.get_embedder_identity()
    assert identity.model_name == "groxaxo/Nemotron-3-Embed-1B-AWQ-W4A16@vllm-2048"
    assert identity.dimension == 2048
    assert embedding._normalize_stored_model_name(identity.model_name) == identity.model_name


def test_fresh_profile_defaults_to_loopback_nemotron(monkeypatch, tmp_path):
    monkeypatch.setenv("MEMPALACE_CONFIG_DIR", str(tmp_path))
    assert MempalaceConfig().embedding_model == "nemotron-vllm"
    ef = embedding.get_embedding_function()
    assert isinstance(ef, NemotronVLLMEmbeddingFunction)
    assert ef._url == "http://127.0.0.1:8000/v1/embeddings"
    assert ef._model == "nemotron-embed"
    assert embedding.get_embedder_identity().dimension == 2048


def test_nemotron_profile_respects_an_explicit_endpoint_and_alias(monkeypatch):
    monkeypatch.setenv("MEMPALACE_EMBEDDING_API_URL", "http://127.0.0.1:9000/v1")
    monkeypatch.setenv("MEMPALACE_EMBEDDING_API_MODEL", "custom-alias")
    ef = embedding.get_embedding_function()
    assert isinstance(ef, NemotronVLLMEmbeddingFunction)
    assert ef._url == "http://127.0.0.1:9000/v1/embeddings"
    assert ef._model == "custom-alias"


def test_misspelled_nemotron_profile_reports_the_correct_name():
    with pytest.raises(embedding.UnknownEmbeddingModelError, match="did you mean 'nemotron-vllm'"):
        embedding.get_embedding_function(model="nemotron-vlm")
