# Progress — Milestone 4

## Completed
- Brasaland full business context loaded as source of truth in `CONTEXT.md` and `CONTEXT.es.md`.
- `memory-bank/` created with `projectbrief.md`, `techContext.md`, and this `progress.md`.
- Root `AGENTS.md` created with mandatory startup reads and pre-commit flow.
- `.agents/rules/monorepo-delivery-guardrails.md` created with explicit always-active scope.
- `.agents/skills/release-readiness-check/SKILL.md` created with single objective, documented inputs, and verifiable acceptance criteria.
- Next.js + TypeScript apps created in `uis/website` and `uis/backoffice`.
- Public website migrated to reusable TypeScript components and Brasaland-aligned sections.
- Shared business logic module implemented in `packages/shared/types/index.ts`.
- Backoffice imports shared logic module (no duplication) and renders computed output in the UI.
- Website aligned against Hito 1 reference repo sections:
  - Added explicit section ids and navigation parity (`que-hacemos`, `caracteristicas`, `contacto`).
  - Added dedicated `/aplicar` route with typed form and client-side validation.
  - Added SEO structured data (Schema.org Restaurant) in website layout.
  - Added legal links and expanded contact CTA parity.
- Validation completed:
  - `uis/website`: `npm run build` OK.
  - `uis/backoffice`: `npm run build` OK (webpack mode for local shared package compatibility).
  - `uis/website`: `npm run lint` OK after Hito 1 alignment.
  - `uis/website`: `npm run build` OK after Hito 1 alignment.

## In Progress
- None; DEV-55 implementation, evidence and live verification are complete and published for review.

## DEV-55 Implemented and Verified
- User approved adding asynchronous menu batch imports instead of breaking existing catalog GET contracts; no heavy existing pipeline exists in this demo.
- Added shared SQLite catalog/batch storage, atomic idempotent updates, persistent DLQ, and cross-process cache invalidation.
- Celery queues only the batch UUID, tracks started state, logs attempt/status/error/duration, retries at 2/4/8s, and stores terminal failure after initial attempt + 3 retries.
- Added authenticated POST /menu/imports (202), GET /tasks/{UUID}, GET /tasks/dead-letter; worker never runs inside FastAPI.
- Root Compose includes official Redis AOF/noeviction, independent worker, API and Flower. No protected paths modified.
- User approved optional Codespaces Compose override after bridge TCP failures; shared network namespace preserves separate processes.
- 22 unit tests pass. Real demo: 1000 rows accepted in 58.207ms; message contains only UUID; pending, STARTED/SUCCESS events and HTTP success/failure verified.
- Worker completed the batch with API stopped; failing task c0ce9c02-ab07-46db-b134-52673b9ae7da reached SQLite DLQ at attempt 4 with error and UTC timestamp.
- Flower accessible on localhost:5555; service/root READMEs and docs/DEV-55.md document startup/shutdown, evidence and production limitations.
- User authorized commit, push to origin (4GeeksAcademy/ai-engineering-company-project-monorepoo), and PR to main with async-tasks label.
- Evidence: docs/dev55-flower.png shows SUCCESS and FAILURE for the task also present in SQLite DLQ; docs/DEV-55.md includes exact retry log excerpt.
- Published implementation commit 78c3388 to the existing branch on origin. PR #4 targets main: https://github.com/4GeeksAcademy/ai-engineering-company-project-monorepoo/pull/4.

## Caching Exercise Completed
- Created branch `feature/caching-optimisation` from the existing clean working branch.
- Baseline build/lint passed for both Next.js apps before edits.
- Backoffice: conditional next/dynamic for SupplierPanel and HrPanel; useMemo([input]) for the canonical aggregated/sorted snapshot.
- FastAPI demo added under `services/catalog-api`: public menu/locations, TTL 60s/300s, atomic per-family invalidation, bounded country keys, timing middleware and disabled-by-default authorized writes.
- No protected files changed and no shared business rules duplicated; website unchanged.
- API validation: 11 unittest tests passed, including exact expiration, concurrency and no secret leakage.
- UI validation: backoffice lint/build passed; 2 Playwright tests passed on desktop/mobile, with screenshots and on-demand chunk requests.
- Local benchmark: tiny samples showed no meaningful benefit; 10,000 synthetic rows showed about 15-17% lower HTTP medians on HIT. No production traffic claims.
- Report: `CACHING_REPORT.md`; demo run instructions and limitations in service README.
- Existing npm dependency vulnerability warnings and Starlette test-client deprecation recorded, not changed outside scope.
- User explicitly approved committing, pushing to origin and opening a PR to main.

## Next Steps
1. Review DEV-55 PR #4 to main, including approved scope adaptation, retry-count semantics and verification evidence before merging.
2. Connect real persistent public catalog data, measure request frequency/change rates and recalibrate TTL before production.
3. Add production authentication and coordinated invalidation before introducing private data or multiple workers.
