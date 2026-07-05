from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.app.repositories.base import Base, TimestampMixin


class DocumentModel(TimestampMixin, Base):
    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[str] = mapped_column(String(32), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    raw_char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    normalized_char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_format: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    indexing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    indexing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    embedding_dimensions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    chunks: Mapped[list["DocumentChunkModel"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentChunkModel.chunk_index",
    )


class DocumentChunkModel(TimestampMixin, Base):
    __tablename__ = "document_chunks"

    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    strategy: Mapped[str] = mapped_column(String(32), nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    embedding_provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    embedding_dimensions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    embedding_token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    embedding_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    embedding_vector: Mapped[Optional[list[float]]] = mapped_column(Vector(1536), nullable=True)
    embedded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[DocumentModel] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_document_chunks_document_id_chunk_index", "document_id", "chunk_index", unique=True),
        Index(
            "ix_document_chunks_embedding_vector",
            "embedding_vector",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding_vector": "vector_cosine_ops"},
        ),
    )


class CompanyProfileModel(TimestampMixin, Base):
    __tablename__ = "company_profiles"

    company_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    profile_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    competitor_links: Mapped[list["CompetitorRelationshipModel"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        foreign_keys="CompetitorRelationshipModel.company_id",
    )


class CompetitorRelationshipModel(TimestampMixin, Base):
    __tablename__ = "competitor_relationships"

    relationship_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        ForeignKey("company_profiles.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    competitor_company_id: Mapped[str] = mapped_column(
        ForeignKey("company_profiles.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    company: Mapped[CompanyProfileModel] = relationship(
        back_populates="competitor_links",
        foreign_keys=[company_id],
    )

    __table_args__ = (
        Index(
            "ix_competitor_relationships_company_competitor",
            "company_id",
            "competitor_company_id",
            unique=True,
        ),
    )


class RiskEvidenceModel(TimestampMixin, Base):
    __tablename__ = "risk_evidence"

    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        ForeignKey("company_profiles.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    chunk_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    risk_category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TrendEvidenceModel(TimestampMixin, Base):
    __tablename__ = "trend_evidence"

    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        ForeignKey("company_profiles.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    chunk_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    trend_topic: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    document_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    document_date: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
