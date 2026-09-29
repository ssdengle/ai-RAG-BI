# AI Business Intelligence Platform

Production-quality portfolio project built using the approved architecture:

- `FastAPI` backend for APIs and orchestration.
- `Streamlit` frontend for analyst and operator workflows.
- Background `worker` service for asynchronous jobs.
- `scheduler` service for recurring tasks.
- `PostgreSQL` as the system of record.
- `Redis` for caching and task coordination.
- Enterprise RAG, multi-agent workflows, and evaluation pipelines.

## Platform Status

| Sprint | Scope | Status |
|--------|-------|--------|
| 1–6 | Backend API, RAG, BI, workflows, evaluation, auth, RBAC | Complete |
| 7 | Streamlit enterprise dashboard | Complete |
| 8 | Deployment hardening and portfolio polish | Planned |

## Repository Layout

```text
apps/
  api/         FastAPI service
  web/         Streamlit frontend (Sprint 7)
  worker/      Background worker service (planned)
  scheduler/   Scheduled job service (planned)
libs/
  contracts/   Shared data contracts
  prompts/     Versioned prompt assets
  shared/      Shared utilities
```

## Running the Full Platform (Docker Compose)

Start PostgreSQL, Redis, the API, and the Streamlit dashboard:

```bash
cd ai-RAG-BI
docker compose up --build
```

| Service | URL |
|---------|-----|
| Streamlit dashboard | http://localhost:8501 |
| FastAPI docs | http://localhost:8000/docs |
| API health | http://localhost:8000/v1/health/ready |
| Prometheus metrics | http://localhost:8000/metrics |

Run database migrations before first use (from the API container or local shell):

```bash
docker compose exec api alembic upgrade head
```

## Running the Frontend Locally (without Docker)

```bash
pip install .
export API_BASE_URL=http://localhost:8000
streamlit run apps/web/streamlit_app/app.py
```

Ensure the API is running separately on port 8000.

## Logging In

The dashboard supports two authentication modes:

### Username / Password (JWT)

Default development users (from `.env.example`):

| Username | Password | Role |
|----------|----------|------|
| admin | change-me | Administrator |
| analyst | change-me | Analyst |
| reviewer | change-me | Reviewer |
| viewer | change-me | Viewer |

JWT access tokens refresh automatically before expiry. Refresh tokens rotate via the API.

### API Key (optional)

Use the **API Key** tab on the login page with keys from `AUTH_API_KEYS`:

- `admin-key`, `analyst-key`, `reviewer-key`, `viewer-key`

## Navigating the Dashboard

After sign-in, use the sidebar to access role-aware modules:

1. **Dashboard** — documents, chunks, companies, health, recent activity
2. **Knowledge Base** — upload, browse, filter, chunk explorer, indexing visibility
3. **Retrieval** — hybrid search, context preview, citations
4. **Question Answering** — grounded Q&A with confidence and citations
5. **Business Intelligence** — companies, competitors, risks, trends, executive briefs
6. **Workflow Center** — run and inspect LangGraph workflows
7. **Evaluation** — benchmark datasets, runs, reports, scorer charts
8. **Monitoring** — health checks and Prometheus metrics
9. **Administration** — environment and provider settings (admin only)

Role permissions mirror backend RBAC. Viewers have read-only access; analysts can upload documents and run workflows; reviewers can manage workflows; admins see all modules.

## Frontend Architecture

```text
Streamlit UI (apps/web/streamlit_app/)
    │
    ├── pages/           Route modules (Dashboard, KB, BI, …)
    ├── components/      Reusable UI widgets (layout, citations, auth)
    ├── view_models/     Presentation models derived from API responses
    ├── api_client/      Typed HTTP client (JWT, retries, error mapping)
    └── utils/           Session state, JWT claims, role helpers
            │
            ▼
    FastAPI REST API (apps/api/) — all business logic stays on the backend
```

The frontend never imports repositories or services. Every operation calls existing `/v1/` REST endpoints.

## Example Screenshots

Placeholder assets live in `apps/web/streamlit_app/assets/`. Add screenshots there for portfolio documentation:

- `dashboard.png` — overview metrics and health
- `knowledge-base.png` — document browser and chunk explorer
- `workflow-center.png` — workflow trace and agent timeline

## Running Tests

Backend and frontend tests:

```bash
pytest apps/api/tests apps/web/tests -q
```

## Runtime Target

Python `3.11` is the supported runtime for both API and web services.
