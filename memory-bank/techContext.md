# Technical Context — Milestone 4, Caching and DEV-55

## Monorepo Structure Decisions
- Public frontend lives in `uis/website` (Next.js + TypeScript).
- Internal frontend lives in `uis/backoffice` (Next.js + TypeScript), with independent layout and UX.
- APIs and backend services must be created under `services/`.
- Shared TypeScript domain logic should remain in a single canonical module and be imported by apps to avoid duplication.

## Architecture Direction
- Start with modular monolith principles in the monorepo.
- Prioritize shared domain contracts and reusable UI/domain components.
- Keep business logic separate from rendering logic.
- Backoffice must display business-logic output in UI (not only console).

## Current Technical Risks
- `services/catalog-api` now contains a FastAPI public catalog demo, not a centralized production API.
- Demo catalog overrides, import batches and DLQ persist in shared local SQLite; no POS integration.
- Catalog TTL cache is process-local; persistent family revisions invalidate changes from other processes.
- DEV-55 adds POST /menu/imports (admin, 202 + UUID), GET /tasks/{UUID} and GET /tasks/dead-letter.
- Celery/Flower use REDIS_URL for broker and results; independent worker with late ACK, soft/hard 50s/60s limits.
- max_retries=3 means 4 attempts, backoff 2/4/8s; terminal failures persist in SQLite DLQ. Redis result TTL is 24h.
- Root Compose provides Redis AOF/noeviction, API, worker and Flower. Ports 6379/8000/5555 bind loopback.
- Optional docker-compose.codespaces.yml shares Redis network namespace to bypass this environment's blocked bridge TCP.
- SQLite is single-host development storage. No outbox or automatic poison-task limit for repeated SIGKILL/OOM; see service README.
- Public catalog TTL: menu 60s, locations 300s; authorized writes invalidate the entire affected family atomically.
- Backoffice uses immutable sample input and the canonical shared snapshot; supplier/HR panels load on selection.
- New frontend apps must avoid drift in domain assumptions.
- Cross-app imports require explicit, stable module boundaries.

## Caching Validation
- API: `cd services/catalog-api && python -m unittest -v test_main test_storage` (22 tests).
- DEV-55 integration: start Compose with CATALOG_ADMIN_TOKEN exported; run `python services/catalog-api/verify_async.py`.
- In this Codespaces use `export COMPOSE_FILE=docker-compose.yml:docker-compose.codespaces.yml` before Compose.
- UI: build/lint then start on port 3001 and run `npm --prefix uis/backoffice run test:ui` (desktop/mobile).
- Timing/benchmark methodology, security limits and tradeoffs are documented in `CACHING_REPORT.md`.

## Enforced Guardrails
- Agent reads memory-bank before coding.
- No protected-file edits without explicit confirmation.
- Mandatory validation flow before commit.
- Skills and rules must remain aligned with `CONTEXT.md`.
