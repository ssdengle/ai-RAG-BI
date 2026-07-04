from __future__ import annotations

import asyncio
from collections.abc import Sequence

from apps.api.app.core.errors import ExternalServiceError
from apps.api.app.core.logging import get_logger
from apps.api.app.domain.documents import PersistedDocumentChunk
from apps.api.app.rag.embeddings import EmbeddingProvider, GeneratedChunkEmbedding


class EmbeddingGenerationService:
    def __init__(
        self,
        *,
        provider: EmbeddingProvider,
        batch_size: int,
        max_retries: int,
    ) -> None:
        self._provider = provider
        self._batch_size = max(1, batch_size)
        self._max_retries = max(1, max_retries)
        self._logger = get_logger("api.embedding_service")

    async def generate_for_chunks(
        self,
        chunks: Sequence[PersistedDocumentChunk],
    ) -> list[GeneratedChunkEmbedding]:
        generated_embeddings: list[GeneratedChunkEmbedding] = []

        for start_index in range(0, len(chunks), self._batch_size):
            batch = list(chunks[start_index : start_index + self._batch_size])
            batch_result = await self._embed_with_retries([chunk.text for chunk in batch])
            token_counts = _distribute_integer_usage(
                total=batch_result.usage.prompt_tokens,
                weights=[len(chunk.text) for chunk in batch],
            )
            cost_allocations = _distribute_float_usage(
                total=batch_result.usage.total_cost_usd,
                weights=[len(chunk.text) for chunk in batch],
            )

            for index, chunk in enumerate(batch):
                generated_embeddings.append(
                    GeneratedChunkEmbedding(
                        chunk_id=chunk.chunk_id,
                        vector=batch_result.vectors[index],
                        provider=batch_result.provider,
                        model=batch_result.model,
                        dimensions=batch_result.dimensions,
                        token_count=token_counts[index],
                        cost_usd=cost_allocations[index],
                    )
                )

        return generated_embeddings

    async def _embed_with_retries(self, texts: list[str]):
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                return await self._provider.embed_texts(texts)
            except ExternalServiceError as exc:
                last_error = exc
                self._logger.warning(
                    "embedding.batch_retry",
                    attempt=attempt,
                    batch_size=len(texts),
                    details=exc.details,
                )
                if attempt == self._max_retries:
                    break
                await asyncio.sleep(min(0.25 * attempt, 1.0))

        raise ExternalServiceError(
            "Embedding generation failed after retries.",
            details=str(last_error) if last_error is not None else None,
            code="embedding_generation_failed",
        ) from last_error


def _distribute_integer_usage(total: int | None, weights: list[int]) -> list[int | None]:
    if total is None:
        return [None for _ in weights]

    if not weights:
        return []

    weight_sum = sum(max(weight, 1) for weight in weights)
    allocations = [int(total * (max(weight, 1) / weight_sum)) for weight in weights]
    remainder = total - sum(allocations)

    for index in range(remainder):
        allocations[index % len(allocations)] += 1

    return allocations


def _distribute_float_usage(total: float | None, weights: list[int]) -> list[float | None]:
    if total is None:
        return [None for _ in weights]

    if not weights:
        return []

    weight_sum = sum(max(weight, 1) for weight in weights)
    return [round(total * (max(weight, 1) / weight_sum), 8) for weight in weights]
