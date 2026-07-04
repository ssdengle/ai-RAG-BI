from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.app.api.qa import get_question_answering_service, get_retrieval_service
from apps.api.app.core.database import get_db_session
from apps.api.app.domain.retrieval import AssembledContext, Citation, QuestionAnswerResult, RetrievalResult, RetrievedChunk
from apps.api.app.main import create_app
from apps.api.tests.conftest import FakeDatabaseManager, FakeRedisManager, build_test_settings


class _FakeRetrievalService:
    async def retrieve(self, session, *, query, mode, filters, top_k):
        chunk = RetrievedChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            document_title="Quarterly Report",
            text="Revenue increased in Q1.",
            score=0.9,
            semantic_score=0.9,
            page_number=2,
            document_metadata={"company": "Acme"},
            chunk_metadata={"page_number": 2},
        )
        citation = Citation(
            document_id="doc-1",
            title="Quarterly Report",
            chunk_id="chunk-1",
            page_number=2,
            score=0.9,
            snippet="Revenue increased in Q1.",
        )
        return RetrievalResult(
            mode=mode,
            query=query,
            chunks=[chunk],
            citations=[citation],
            total_candidates=1,
        )


class _FakeQuestionAnsweringService:
    async def answer(self, session, *, question, mode, filters, top_k):
        chunk = RetrievedChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            document_title="Quarterly Report",
            text="Revenue increased in Q1.",
            score=0.9,
            semantic_score=0.9,
            page_number=2,
        )
        citation = Citation(
            document_id="doc-1",
            title="Quarterly Report",
            chunk_id="chunk-1",
            page_number=2,
            score=0.9,
            snippet="Revenue increased in Q1.",
        )
        retrieval = RetrievalResult(
            mode=mode,
            query=question,
            chunks=[chunk],
            citations=[citation],
            total_candidates=1,
        )
        context = AssembledContext(
            text="[SOURCE document_id=doc-1] Revenue increased in Q1.",
            citations=[citation],
            chunk_count=1,
            truncated=False,
        )
        return QuestionAnswerResult(
            answer="Revenue increased in Q1.",
            citations=[citation],
            confidence=0.9,
            retrieval=retrieval,
            context=context,
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            finish_reason="stop",
        )


async def _override_db_session():
    yield None


def _build_test_app():
    app = create_app(
        settings=build_test_settings(),
        database_manager=FakeDatabaseManager(),
        redis_manager=FakeRedisManager(),
        perform_startup_checks=False,
    )
    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[get_retrieval_service] = lambda: _FakeRetrievalService()
    app.dependency_overrides[get_question_answering_service] = lambda: _FakeQuestionAnsweringService()
    return app


def test_search_documents_endpoint_returns_chunks_and_citations() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.post(
            "/v1/retrieval/search",
            json={"query": "revenue", "mode": "hybrid", "top_k": 5, "filters": {}},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["chunks"][0]["chunk_id"] == "chunk-1"
    assert payload["citations"][0]["document_id"] == "doc-1"


def test_preview_retrieved_context_endpoint_returns_context() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.post(
            "/v1/retrieval/context-preview",
            json={"query": "revenue", "mode": "hybrid", "top_k": 5, "filters": {}},
        )

    assert response.status_code == 200
    assert "Revenue increased in Q1." in response.json()["context"]


def test_ask_question_endpoint_returns_grounded_answer() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.post(
            "/v1/qa/ask",
            json={"query": "What happened to revenue?", "mode": "hybrid", "top_k": 5, "filters": {}},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Revenue increased in Q1."
    assert payload["citations"][0]["chunk_id"] == "chunk-1"


def test_ask_question_within_document_endpoint_returns_grounded_answer() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.post(
            "/v1/qa/ask/document/doc-1",
            json={"query": "What happened to revenue?", "mode": "semantic", "top_k": 5, "filters": {}},
        )

    assert response.status_code == 200
    assert response.json()["answer"] == "Revenue increased in Q1."


def test_ask_question_across_selected_documents_endpoint_returns_grounded_answer() -> None:
    with TestClient(_build_test_app()) as client:
        response = client.post(
            "/v1/qa/ask/documents",
            json={
                "query": "What happened to revenue?",
                "mode": "hybrid",
                "top_k": 5,
                "document_ids": ["doc-1", "doc-2"],
                "filters": {},
            },
        )

    assert response.status_code == 200
    assert response.json()["retrieval"]["query"] == "What happened to revenue?"
