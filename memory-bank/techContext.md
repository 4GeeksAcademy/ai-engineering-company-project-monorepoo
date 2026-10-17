# Technical Context — Milestone 4 and Caching Exercise

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
- Demo catalog/cache live in process; one worker only, no persistence or POS integration.
- Public catalog TTL: menu 60s, locations 300s; authorized writes invalidate the entire affected family atomically.
- Backoffice uses immutable sample input and the canonical shared snapshot; supplier/HR panels load on selection.
- New frontend apps must avoid drift in domain assumptions.
- Cross-app imports require explicit, stable module boundaries.

## Caching Validation
- API: `cd services/catalog-api && python -m unittest -v test_main` (11 tests).
- UI: build/lint then start on port 3001 and run `npm --prefix uis/backoffice run test:ui` (desktop/mobile).
- Timing/benchmark methodology, security limits and tradeoffs are documented in `CACHING_REPORT.md`.

## Enforced Guardrails
- Agent reads memory-bank before coding.
- No protected-file edits without explicit confirmation.
- Mandatory validation flow before commit.
- Skills and rules must remain aligned with `CONTEXT.md`.
