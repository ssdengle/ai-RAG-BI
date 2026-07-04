from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.app.core.errors import DomainError, ExternalServiceError, ValidationError
from apps.api.app.domain.documents import ChunkingOptions
from apps.api.app.rag.exceptions import (
    EmptyDocumentError,
    MissingParserDependencyError,
    UnsupportedDocumentTypeError,
)
from apps.api.app.rag.service import DocumentIngestionService
from apps.api.app.schemas.rag import (
    ChunkResponse,
    DocumentMetadataResponse,
    IngestionPreviewRequest,
    IngestionPreviewResponse,
)


router = APIRouter(prefix="/v1/rag", tags=["rag"])


def get_document_ingestion_service() -> DocumentIngestionService:
    return DocumentIngestionService()


@router.post("/ingestion/preview", response_model=IngestionPreviewResponse)
def preview_ingestion(
    payload: IngestionPreviewRequest,
    ingestion_service: DocumentIngestionService = Depends(get_document_ingestion_service),
) -> IngestionPreviewResponse:
    try:
        result = ingestion_service.ingest(
            filename=payload.filename,
            content_type=payload.content_type,
            content=payload.content.encode("utf-8"),
            options=ChunkingOptions(
                strategy=payload.strategy,
                max_chunk_size=payload.max_chunk_size,
                overlap_size=payload.overlap_size,
                window_size=payload.window_size,
                step_size=payload.step_size,
            ),
        )
    except UnsupportedDocumentTypeError as exc:
        raise DomainError(
            "Unsupported document type.",
            details=str(exc),
            code="unsupported_document_type",
            status_code=415,
        ) from exc
    except MissingParserDependencyError as exc:
        raise ExternalServiceError(
            "A required document parser dependency is unavailable.",
            details=str(exc),
            code="parser_dependency_missing",
            status_code=500,
        ) from exc
    except EmptyDocumentError as exc:
        raise ValidationError(
            "The document did not contain usable text.",
            details=str(exc),
            code="empty_document",
        ) from exc
    except ValueError as exc:
        raise ValidationError(
            "Invalid ingestion request.",
            details=str(exc),
            code="invalid_ingestion_request",
        ) from exc

    return IngestionPreviewResponse(
        metadata=DocumentMetadataResponse.model_validate(result.metadata.__dict__),
        normalized_text=result.normalized_text,
        chunk_count=len(result.chunks),
        chunks=[
            ChunkResponse.model_validate(
                {
                    **chunk.__dict__,
                    "strategy": chunk.strategy,
                }
            )
            for chunk in result.chunks
        ],
    )
