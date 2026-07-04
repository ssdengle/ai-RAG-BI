class RAGIngestionError(Exception):
    """Base exception for ingestion failures."""


class UnsupportedDocumentTypeError(RAGIngestionError):
    """Raised when no parser is registered for a file type."""


class MissingParserDependencyError(RAGIngestionError):
    """Raised when a parser dependency is not installed."""


class EmptyDocumentError(RAGIngestionError):
    """Raised when extraction produces no meaningful text."""
