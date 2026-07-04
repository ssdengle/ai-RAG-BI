from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class EmbeddingBatchUsage:
    prompt_tokens: int | None = None
    total_cost_usd: float | None = None


@dataclass(frozen=True)
class EmbeddingBatchResult:
    vectors: list[list[float]]
    provider: str
    model: str
    dimensions: int
    usage: EmbeddingBatchUsage = field(default_factory=EmbeddingBatchUsage)


@dataclass(frozen=True)
class GeneratedChunkEmbedding:
    chunk_id: str
    vector: list[float]
    provider: str
    model: str
    dimensions: int
    token_count: int | None = None
    cost_usd: float | None = None


class EmbeddingProvider(Protocol):
    async def embed_texts(self, texts: list[str]) -> EmbeddingBatchResult:
        """Generate embeddings for a batch of texts."""
