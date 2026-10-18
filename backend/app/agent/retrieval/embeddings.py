"""Эмбеддинги для schema linking. Запрос и документы — одной и той же моделью."""

import hashlib
import math
from typing import Protocol

from app.agent.retrieval.sparse import tokenize


class Embedder(Protocol):
    name: str
    dimension: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


OPENAI_DIMENSIONS = {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072}


class OpenAIEmbedder:
    def __init__(self, model: str, api_key: str) -> None:
        from openai import AsyncOpenAI

        self.name = model
        self.dimension = OPENAI_DIMENSIONS[model]
        self._client = AsyncOpenAI(api_key=api_key)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), 256):
            batch = texts[start : start + 256]
            response = await self._client.embeddings.create(model=self.name, input=batch)
            vectors.extend(d.embedding for d in response.data)
        return vectors


class HashEmbedder:
    """Детерминированные «эмбеддинги» из хэшей токенов — для тестов без сети."""

    def __init__(self, dimension: int = 256) -> None:
        self.name = f"hash-{dimension}"
        self.dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        result = []
        for text in texts:
            vector = [0.0] * self.dimension
            for token in tokenize(text):
                h = int(hashlib.md5(token.encode()).hexdigest(), 16)
                vector[h % self.dimension] += 1.0
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            result.append([v / norm for v in vector])
        return result
