from __future__ import annotations

from typing import Any


def build_openapi_schema(app) -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["info"]["contact"] = {"name": "Platform Engineering", "email": "platform@example.com"}
    schema["info"]["license"] = {"name": "Proprietary"}
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT access token obtained from /v1/auth/login.",
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Service API key configured by platform administrators.",
        },
    }
    schema["security"] = [{"BearerAuth": []}, {"ApiKeyAuth": []}]
    _apply_examples(schema)
    app.openapi_schema = schema
    return app.openapi_schema


def _apply_examples(schema: dict[str, Any]) -> None:
    paths = schema.setdefault("paths", {})
    _add_example(
        paths,
        "/v1/auth/login",
        "post",
        request={
            "username": "analyst",
            "password": "change-me",
        },
        response={
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "expires_in": 3600,
        },
        description="Authenticate with username and password to receive JWT tokens.",
    )
    _add_example(
        paths,
        "/v1/retrieval/search",
        "post",
        request={
            "query": "What happened to revenue in Q1?",
            "mode": "hybrid",
            "top_k": 5,
            "filters": {"company": "Acme"},
        },
        response={
            "mode": "hybrid",
            "query": "What happened to revenue in Q1?",
            "total_candidates": 12,
            "chunks": [
                {
                    "chunk_id": "chunk-1",
                    "document_id": "doc-1",
                    "document_title": "Annual Report",
                    "text": "Revenue increased steadily.",
                    "score": 0.91,
                }
            ],
        },
        description="Search indexed documents using semantic, keyword, or hybrid retrieval.",
    )
    _add_example(
        paths,
        "/v1/qa/ask",
        "post",
        request={
            "question": "Summarize the primary revenue drivers.",
            "mode": "hybrid",
            "top_k": 5,
        },
        response={
            "answer": "Revenue increased due to expansion in core product lines.",
            "confidence": 0.88,
            "citations": [
                {
                    "document_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "snippet": "Revenue increased steadily.",
                    "score": 0.91,
                }
            ],
        },
        description="Ask a grounded question across the knowledge base.",
    )
    _add_example(
        paths,
        "/v1/workflows/run",
        "post",
        request={
            "user_request": "Summarize market trends and risks for Acme.",
            "topic": "Market outlook",
            "company_id": "company-1",
        },
        response={
            "workflow_id": "wf-123",
            "status": "completed",
            "confidence": 0.9,
            "final_output": {"summary": "Acme revenue increased with manageable risk exposure."},
        },
        description="Execute a multi-agent workflow for business intelligence analysis.",
    )


def _add_example(
    paths: dict[str, Any],
    route: str,
    method: str,
    *,
    request: dict[str, Any],
    response: dict[str, Any],
    description: str,
) -> None:
    operation = paths.setdefault(route, {}).setdefault(method, {})
    operation["description"] = description
    operation.setdefault("requestBody", {}).setdefault("content", {}).setdefault("application/json", {})[
        "example"
    ] = request
    operation.setdefault("responses", {}).setdefault("200", {}).setdefault("content", {}).setdefault(
        "application/json", {}
    )["example"] = response
