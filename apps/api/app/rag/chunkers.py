from __future__ import annotations

import hashlib
import re

from apps.api.app.domain.documents import ChunkingOptions, DocumentChunk
from apps.api.app.rag.interfaces import ChunkingStrategy


_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


class RecursiveChunker:
    name = "recursive"
    _separators = ("\n\n", "\n", ". ", " ")

    def chunk(
        self,
        *,
        document_id: str,
        text: str,
        options: ChunkingOptions,
    ) -> list[DocumentChunk]:
        parts = self._split_recursive(text, max_size=options.max_chunk_size, depth=0)
        return _build_chunks(
            document_id=document_id,
            strategy=self.name,
            text=text,
            parts=parts,
        )

    def _split_recursive(self, text: str, *, max_size: int, depth: int) -> list[str]:
        text = text.strip()
        if not text:
            return []

        if len(text) <= max_size:
            return [text]

        if depth >= len(self._separators):
            return [text[index : index + max_size].strip() for index in range(0, len(text), max_size)]

        separator = self._separators[depth]
        if separator not in text:
            return self._split_recursive(text, max_size=max_size, depth=depth + 1)

        pieces = text.split(separator)
        chunks: list[str] = []
        buffer = ""
        joiner = separator if separator != " " else " "

        for piece in pieces:
            candidate = f"{buffer}{joiner if buffer else ''}{piece}".strip()
            if len(candidate) <= max_size:
                buffer = candidate
                continue

            if buffer:
                chunks.extend(self._split_recursive(buffer, max_size=max_size, depth=depth + 1))
            buffer = piece.strip()

            if len(buffer) > max_size:
                chunks.extend(self._split_recursive(buffer, max_size=max_size, depth=depth + 1))
                buffer = ""

        if buffer:
            chunks.extend(self._split_recursive(buffer, max_size=max_size, depth=depth + 1))

        return [chunk for chunk in chunks if chunk]


class SemanticChunker:
    name = "semantic"

    def chunk(
        self,
        *,
        document_id: str,
        text: str,
        options: ChunkingOptions,
    ) -> list[DocumentChunk]:
        paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
        parts: list[str] = []
        current = ""

        for paragraph in paragraphs:
            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(candidate) <= options.max_chunk_size:
                current = candidate
                continue

            if current:
                parts.append(current)
            current = ""

            sentences = [sentence.strip() for sentence in _SENTENCE_BOUNDARY_RE.split(paragraph) if sentence.strip()]
            sentence_buffer = ""
            for sentence in sentences:
                sentence_candidate = f"{sentence_buffer} {sentence}".strip() if sentence_buffer else sentence
                if len(sentence_candidate) <= options.max_chunk_size:
                    sentence_buffer = sentence_candidate
                    continue

                if sentence_buffer:
                    parts.append(sentence_buffer)
                sentence_buffer = sentence

            if sentence_buffer:
                current = sentence_buffer

        if current:
            parts.append(current)

        return _build_chunks(
            document_id=document_id,
            strategy=self.name,
            text=text,
            parts=parts,
        )


class SlidingWindowChunker:
    name = "sliding_window"

    def chunk(
        self,
        *,
        document_id: str,
        text: str,
        options: ChunkingOptions,
    ) -> list[DocumentChunk]:
        words = text.split()
        if not words:
            return []

        window_size = max(1, options.window_size)
        step_size = max(1, options.step_size)
        parts: list[str] = []

        for start in range(0, len(words), step_size):
            segment = words[start : start + window_size]
            if not segment:
                break

            parts.append(" ".join(segment))

            if start + window_size >= len(words):
                break

        return _build_chunks(
            document_id=document_id,
            strategy=self.name,
            text=text,
            parts=parts,
        )


class ChunkingStrategyRegistry:
    def __init__(self, strategies: list[ChunkingStrategy]) -> None:
        self._strategies = {strategy.name: strategy for strategy in strategies}

    def resolve(self, strategy_name: str) -> ChunkingStrategy:
        try:
            return self._strategies[strategy_name]
        except KeyError as exc:
            available = ", ".join(sorted(self._strategies))
            raise ValueError(f"Unsupported chunking strategy '{strategy_name}'. Available: {available}.") from exc


def build_default_chunking_registry() -> ChunkingStrategyRegistry:
    return ChunkingStrategyRegistry(
        strategies=[
            RecursiveChunker(),
            SemanticChunker(),
            SlidingWindowChunker(),
        ]
    )


def _build_chunks(
    *,
    document_id: str,
    strategy: str,
    text: str,
    parts: list[str],
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    cursor = 0

    for index, part in enumerate(part for part in parts if part.strip()):
        start_offset = text.find(part, cursor)
        if start_offset == -1:
            start_offset = max(0, cursor)

        end_offset = start_offset + len(part)
        cursor = end_offset
        chunk_id = hashlib.sha256(f"{document_id}:{strategy}:{index}:{part}".encode("utf-8")).hexdigest()

        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                document_id=document_id,
                index=index,
                text=part,
                strategy=strategy,  # type: ignore[arg-type]
                start_offset=start_offset,
                end_offset=end_offset,
                metadata={"character_count": len(part), "word_count": len(part.split())},
            )
        )

    return chunks
