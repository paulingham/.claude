---
task_id: auth-demo-001
phase: intake
gate: exploration
ambiguity_score: 2
timestamp: 2026-03-30T21:00:00Z
---

## Discussion: User Authentication with Google OAuth + React SPA

### Questions Asked
| # | Question | Category | Decision |
|---|----------|----------|----------|
| 1 | Monorepo or separate repos? | approach | Monorepo — `api/` + `web/` in same repo |
| 2 | Express + Vite React, or Next.js full-stack? | approach | Express + Vite React — clear API/UI separation |
| 3 | JWT stateless only, or JWT + refresh tokens stored in DB? | approach | JWT (15min access) + refresh tokens (7 days) in SQLite via Prisma |
| 4 | Bearer tokens in headers, or session cookies? | approach | Bearer tokens — standard REST API practice |
| 5 | Real Google OAuth credentials or placeholder env vars? | data | Placeholder env vars (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET) |
| 6 | ORM and test stack? | integration | Prisma + SQLite (DB), Jest + Supertest (API), Vitest + RTL (UI) |

### Decisions Summary
- Architecture: Monorepo with `api/` (Express/TypeScript) and `web/` (Vite/React/TypeScript)
- Auth strategy: JWT access tokens (15min) + refresh tokens (7 days) in DB
- Transport: Bearer tokens via Authorization header
- Google OAuth: Passport.js google strategy, placeholder credentials
- DB: SQLite + Prisma ORM (zero-config, portable)
- Testing: Jest + Supertest for API contracts, Vitest + RTL for React

### Impact on Implementation
- Approach: Monorepo, two independent build targets
- Integration point: API on port 3001, React dev server on port 5173 (Vite default)
- Data assumptions: Google OAuth uses PKCE flow, redirect to frontend callback route
- Stories can be built independently: API stories (no frontend dep) + UI stories (mock API in tests)
