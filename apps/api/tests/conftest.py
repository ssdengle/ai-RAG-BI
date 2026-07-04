from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pytest

from apps.api.app.core.config import (
    AppSettings,
    DatabaseSettings,
    LLMSettings,
    LoggingSettings,
    RedisSettings,
    Settings,
)
from apps.api.app.core.errors import InfrastructureError
from apps.api.app.domain.documents import IndexingStatus, PersistedDocument, PersistedDocumentChunk


class FakeDatabaseManager:
    def __init__(self, *, health_error: Optional[InfrastructureError] = None) -> None:
        self.health_error = health_error
        self.initialize_calls: list[bool] = []
        self.disposed = False

    async def initialize(self, *, check_connection: bool = True) -> None:
        self.initialize_calls.append(check_connection)
        if check_connection and self.health_error is not None:
            raise self.health_error

    async def check_connection(self) -> None:
        if self.health_error is not None:
            raise self.health_error

    async def dispose(self) -> None:
        self.disposed = True


class FakeRedisManager:
    def __init__(self, *, health_error: Optional[InfrastructureError] = None) -> None:
        self.health_error = health_error
        self.initialize_calls: list[bool] = []
        self.closed = False

    async def initialize(self, *, check_connection: bool = True) -> None:
        self.initialize_calls.append(check_connection)
        if check_connection and self.health_error is not None:
            raise self.health_error

    async def ping(self) -> None:
        if self.health_error is not None:
            raise self.health_error

    async def close(self) -> None:
        self.closed = True


def build_test_settings() -> Settings:
    return Settings(
        app=AppSettings(name="ai-business-intelligence-platform", environment="test", host="127.0.0.1", port=8000),
        database=DatabaseSettings(
            host="postgres",
            port=5432,
            database="ai_bi_platform",
            username="ai_bi_user",
            password="change-me",
            echo=False,
            pool_size=5,
            max_overflow=10,
            connect_timeout_seconds=5,
        ),
        redis=RedisSettings(
            host="redis",
            port=6379,
            database=0,
            password=None,
            max_connections=20,
        ),
        logging=LoggingSettings(level="INFO", json_logs=False, service_name="api-test"),
        llm=LLMSettings(
            provider="openai",
            model="gpt-4o-mini",
            api_key=None,
            base_url=None,
            timeout_seconds=30,
            embedding_model="text-embedding-3-small",
            embedding_dimensions=1536,
            embedding_batch_size=32,
            embedding_max_retries=3,
        ),
    )


@pytest.fixture
def test_settings() -> Settings:
    return build_test_settings()


def build_persisted_document(
    *,
    document_id: str = "doc-1",
    title: str = "Analysis",
    chunk_count: int = 2,
    indexing_status: IndexingStatus = IndexingStatus.PENDING,
    indexing_error: Optional[str] = None,
    attributes: Optional[dict[str, object]] = None,
    embedding_provider: Optional[str] = None,
    embedding_model: Optional[str] = None,
    embedding_dimensions: Optional[int] = None,
    indexed_at: Optional[datetime] = None,
) -> PersistedDocument:
    now = datetime.now(timezone.utc)
    return PersistedDocument(
        document_id=document_id,
        filename="analysis.txt",
        extension=".txt",
        mime_type="text/plain",
        checksum_sha256="abc123",
        size_bytes=100,
        title=title,
        raw_char_count=80,
        normalized_char_count=75,
        word_count=10,
        source_format="txt",
        normalized_text="Revenue increased steadily.",
        attributes=attributes or {"source": "upload"},
        chunk_count=chunk_count,
        indexing_status=indexing_status,
        indexing_error=indexing_error,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        indexed_at=indexed_at,
        created_at=now,
        updated_at=now,
    )


def build_persisted_chunk(
    *,
    chunk_id: str = "chunk-1",
    document_id: str = "doc-1",
    index: int = 0,
    metadata: Optional[dict[str, object]] = None,
    embedding_vector: Optional[list[float]] = None,
    embedding_provider: Optional[str] = None,
    embedding_model: Optional[str] = None,
    embedding_dimensions: Optional[int] = None,
    embedding_token_count: Optional[int] = None,
    embedding_cost_usd: Optional[float] = None,
    embedded_at: Optional[datetime] = None,
) -> PersistedDocumentChunk:
    now = datetime.now(timezone.utc)
    return PersistedDocumentChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        index=index,
        text="Revenue increased steadily.",
        strategy="semantic",
        start_offset=0,
        end_offset=28,
        metadata=metadata or {"character_count": 28},
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        embedding_token_count=embedding_token_count,
        embedding_cost_usd=embedding_cost_usd,
        embedding_vector=embedding_vector,
        embedded_at=embedded_at,
        created_at=now,
        updated_at=now,
    )
