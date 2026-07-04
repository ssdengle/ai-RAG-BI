from __future__ import annotations

import hashlib
from pathlib import Path

from apps.api.app.domain.documents import ChunkingOptions, DocumentMetadata, IngestedDocument
from apps.api.app.rag.chunkers import (
    ChunkingStrategyRegistry,
    build_default_chunking_registry,
)
from apps.api.app.rag.exceptions import EmptyDocumentError
from apps.api.app.rag.parsers import DocumentParserRegistry, build_default_parser_registry
from apps.api.app.rag.processing import TextCleaner, TextNormalizer


class DocumentIngestionService:
    def __init__(
        self,
        *,
        parser_registry: DocumentParserRegistry | None = None,
        chunking_registry: ChunkingStrategyRegistry | None = None,
        cleaner: TextCleaner | None = None,
        normalizer: TextNormalizer | None = None,
    ) -> None:
        self._parser_registry = parser_registry or build_default_parser_registry()
        self._chunking_registry = chunking_registry or build_default_chunking_registry()
        self._cleaner = cleaner or TextCleaner()
        self._normalizer = normalizer or TextNormalizer()

    def ingest(
        self,
        *,
        filename: str,
        content_type: str | None,
        content: bytes,
        options: ChunkingOptions,
        document_id: str | None = None,
        additional_attributes: dict[str, object] | None = None,
    ) -> IngestedDocument:
        parser = self._parser_registry.resolve(filename, content_type)
        parsed_document = parser.parse(filename, content_type, content)

        cleaned_text = self._cleaner.clean(parsed_document.text)
        normalized_text = self._normalizer.normalize(cleaned_text)
        if not normalized_text:
            raise EmptyDocumentError(f"Document '{filename}' did not produce any usable text.")

        checksum_sha256 = hashlib.sha256(content).hexdigest()
        resolved_document_id = document_id or checksum_sha256
        extension = Path(filename).suffix.lower()
        normalized_content_type = (content_type or "application/octet-stream").split(";")[0].strip()
        chunker = self._chunking_registry.resolve(options.strategy)
        chunks = chunker.chunk(
            document_id=resolved_document_id,
            text=normalized_text,
            options=options,
        )

        metadata = DocumentMetadata(
            document_id=resolved_document_id,
            filename=filename,
            extension=extension,
            mime_type=normalized_content_type,
            checksum_sha256=checksum_sha256,
            size_bytes=len(content),
            title=parsed_document.title,
            raw_char_count=len(parsed_document.text),
            normalized_char_count=len(normalized_text),
            word_count=len(normalized_text.split()),
            source_format=parsed_document.extracted_metadata.get("format", extension.lstrip(".")),
            attributes={
                **parsed_document.extracted_metadata,
                **(additional_attributes or {}),
            },
        )

        return IngestedDocument(
            metadata=metadata,
            normalized_text=normalized_text,
            chunks=chunks,
        )
