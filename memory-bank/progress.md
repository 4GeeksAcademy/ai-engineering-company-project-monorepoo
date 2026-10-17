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
- None; caching implementation and validation are complete.

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
1. Review the caching delivery PR to main with AGENTS.md and validation evidence before merging.
2. Connect real persistent public catalog data, measure request frequency/change rates and recalibrate TTL before production.
3. Add production authentication and coordinated invalidation before introducing private data or multiple workers.
