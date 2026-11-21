"""Role-aware embeddings for the local Nemotron AWQ vLLM deployment."""

import json
import math
import threading
from urllib.request import Request, urlopen

from .config import strip_lone_surrogates
from .embedding import (
    _NEMOTRON_VLLM_DIMENSION,
    _NEMOTRON_VLLM_IDENTITY,
    _NEMOTRON_VLLM_MODEL,
    EmbeddingAPIError,
    OpenAICompatEmbeddingFunction,
)
from .llm_client import LLMError, _http_post_json

_MODEL_CONTEXT = 4096
_CHUNK_TOKENS = 3500
_CHUNK_OVERLAP = 250
_TOKENIZER_TIMEOUT = 60


class NemotronVLLMEmbeddingFunction(OpenAICompatEmbeddingFunction):
    def __init__(self, base_url, model, api_key=None):
        super().__init__(base_url, model, api_key)
        self._server_root = self._url.removesuffix("/v1/embeddings")
        self._verified = False
        self._verify_lock = threading.Lock()

    @staticmethod
    def name() -> str:
        return _NEMOTRON_VLLM_IDENTITY

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}

    def _verify_model(self) -> None:
        with self._verify_lock:
            if self._verified:
                return
            url = f"{self._server_root}/v1/models"
            try:
                with urlopen(Request(url, headers=self._headers()), timeout=15) as response:
                    models = json.load(response)["data"]
                model = next(entry for entry in models if entry.get("id") == self._model)
                valid = (
                    model.get("root") == _NEMOTRON_VLLM_MODEL
                    and int(model["max_model_len"]) >= _MODEL_CONTEXT
                )
            except (OSError, KeyError, TypeError, ValueError, AttributeError, StopIteration) as exc:
                raise EmbeddingAPIError(f"Could not verify Nemotron model at {url}") from exc
            if not valid:
                raise EmbeddingAPIError(
                    f"{url} does not serve {_NEMOTRON_VLLM_MODEL} as {self._model!r} "
                    f"with a {_MODEL_CONTEXT}-token context"
                )
            self._verified = True

    def _tokenizer_request(self, route: str, **payload) -> dict:
        url = f"{self._server_root}/{route}"
        try:
            return _http_post_json(
                url, {"model": self._model, **payload}, self._headers(), _TOKENIZER_TIMEOUT
            )
        except LLMError as exc:
            raise EmbeddingAPIError(f"Nemotron tokenizer request failed at {url}: {exc}") from exc

    def _document_windows(self, text: str) -> list[str]:
        text = strip_lone_surrogates(text)
        # A UTF-8 byte budget is conservative for the tokenizer's byte fallback.
        # The actual tokenizer keeps long but compressible text in one window.
        if len(text.encode("utf-8")) <= _CHUNK_TOKENS:
            return [text]
        result = self._tokenizer_request("tokenize", prompt=text, add_special_tokens=False)
        tokens = result.get("tokens") if isinstance(result, dict) else None
        if not isinstance(tokens, list) or not all(type(token) is int for token in tokens):
            raise EmbeddingAPIError("Nemotron tokenizer returned invalid token IDs")
        if len(tokens) <= _CHUNK_TOKENS:
            return [text]
        windows = []
        step = _CHUNK_TOKENS - _CHUNK_OVERLAP
        for start in range(0, len(tokens) - _CHUNK_OVERLAP, step):
            result = self._tokenizer_request(
                "detokenize", tokens=tokens[start : start + _CHUNK_TOKENS]
            )
            window = result.get("prompt") if isinstance(result, dict) else None
            if not isinstance(window, str):
                raise EmbeddingAPIError("Nemotron detokenizer returned invalid text")
            windows.append(window)
        return windows

    def _vectors_from_response(self, data, n: int) -> list:
        vectors = super()._vectors_from_response(data, n)
        for vector in vectors:
            if len(vector) != _NEMOTRON_VLLM_DIMENSION or not math.isclose(
                math.hypot(*vector), 1.0, abs_tol=1e-5
            ):
                raise EmbeddingAPIError(
                    "Nemotron returned a wrong-width, zero, or non-finite vector"
                )
        return vectors

    def _embed_role(self, texts, prefix: str) -> list:
        texts = [texts] if isinstance(texts, str) else list(texts)
        if not texts:
            return []
        self._verify_model()
        windows = [self._document_windows(text) for text in texts]
        vectors = iter(super().__call__([prefix + window for group in windows for window in group]))
        results = []
        for group in windows:
            group_vectors = [next(vectors) for _ in group]
            if len(group_vectors) == 1:
                results.append(group_vectors[0])
                continue
            pooled = [sum(column) for column in zip(*group_vectors)]
            norm = math.hypot(*pooled)
            if not math.isfinite(norm) or norm < 1e-12:
                raise EmbeddingAPIError("Nemotron window vectors cannot be normalized")
            results.append([value / norm for value in pooled])
        return results

    def __call__(self, input):  # noqa: A002 — ChromaDB embedding protocol
        return self._embed_role(input, "passage: ")

    def embed_query(self, input):  # noqa: A002 — ChromaDB embedding protocol
        return self._embed_role(input, "query: ")
