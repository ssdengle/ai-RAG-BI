from __future__ import annotations

from typing import Protocol

from apps.api.app.domain.documents import ChunkingOptions, DocumentChunk, ParsedDocument


class DocumentParser(Protocol):
    supported_extensions: tuple[str, ...]
    supported_mime_types: tuple[str, ...]

    def parse(self, filename: str, content_type: str | None, content: bytes) -> ParsedDocument:
        """Extract text and lightweight metadata from raw file content."""


class ChunkingStrategy(Protocol):
    name: str

    def chunk(
        self,
        *,
        document_id: str,
        text: str,
        options: ChunkingOptions,
    ) -> list[DocumentChunk]:
        """Split normalized text into retrievable chunks."""
