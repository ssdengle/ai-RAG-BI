# AI Business Intelligence Platform

Production-quality portfolio project built using the approved architecture:

- `FastAPI` backend for APIs and orchestration.
- `Streamlit` frontend for analyst and operator workflows.
- Background `worker` service for asynchronous jobs.
- `scheduler` service for recurring tasks.
- `PostgreSQL` as the system of record.
- `Redis` for caching and task coordination.
- Future support for `RAG`, multi-agent workflows, and evaluation pipelines.

## Sprint 1 Scope

Sprint 1 establishes the platform foundation:

1. Repository structure
2. Python project management
3. Service initialization
4. Docker and environment configuration
5. Logging and infrastructure connectivity
6. Health checks and startup verification

## Repository Layout

```text
apps/
  api/         FastAPI service
  web/         Streamlit frontend
  worker/      Background worker service
  scheduler/   Scheduled job service
libs/
  contracts/   Shared data contracts
  prompts/     Versioned prompt assets
  shared/      Shared utilities
infra/
  docker/      Container-related assets
  github/      CI/CD support assets
  terraform/   Infrastructure as code
data/
  seed/        Seed data
  eval_datasets/ Evaluation datasets
docs/
  architecture/ Architecture notes
  adr/          Architecture decision records
  runbooks/     Operational playbooks
scripts/        Development and maintenance scripts
```

## Runtime Target

The project targets Python `3.11` for modern typing support, stronger library compatibility, and a production-ready baseline.