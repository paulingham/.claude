# Tech Stack Decision Matrix

## Decision Process

1. **Classify** the product type
2. **Apply** constraint modifiers (team expertise, timeline, compliance, scale)
3. **Select** stack from the recommendation, adjusted by constraints
4. **Verify** the bootstrap command works before committing

## Product Type → Recommended Stack

| Product Type | Frontend | Backend | Database | Auth | Hosting |
|-------------|----------|---------|----------|------|---------|
| SaaS Dashboard | Next.js (App Router) | Next.js API + separate service | PostgreSQL | Auth.js / Clerk | Vercel + Fly.io |
| Consumer App (web) | Next.js (App Router) | Next.js API routes | PostgreSQL | Auth.js / Clerk | Vercel |
| Consumer App (mobile) | Expo (React Native) | Separate API (Node/Go) | PostgreSQL | Auth0 / Clerk | EAS + Fly.io |
| Content Site / Blog | Astro | Astro (SSG) | Markdown / CMS | — | Cloudflare Pages |
| API-Only Service | — | Node.js (Hono/Fastify) | PostgreSQL | JWT / API keys | Fly.io / Railway |
| E-Commerce | Next.js (App Router) | Next.js + Stripe | PostgreSQL | Auth.js | Vercel |
| Internal Tool | Next.js or Vite+React | Next.js API routes | PostgreSQL | SAML/OIDC | Docker + internal |
| Developer Tool | Vite+React (SPA) or CLI | Node.js (Hono) | SQLite / PostgreSQL | API keys | Fly.io |
| Social Platform | Next.js (App Router) | Separate API (Node/Go) | PostgreSQL + Redis | Auth.js | AWS / Fly.io |
| Real-time App | Next.js + WebSocket | Node.js (Hono/Fastify) | PostgreSQL + Redis | Auth.js | Fly.io |

## Frontend Framework Decision

```
Need SSR or SEO-critical pages?
  → YES: Next.js (App Router)
  → NO: Is it a static/content site?
    → YES: Astro
    → NO: Is it a SPA dashboard/admin?
      → YES: Vite + React
      → NO: Is it mobile?
        → YES: Expo (React Native)
        → NO: Is it multi-platform (web + mobile)?
          → YES: Expo for mobile + Next.js for web
          → NO: Default to Next.js (most versatile)
```

## Backend Framework Decision

```
TypeScript team?
  → Modern API: Hono (lightweight, edge-ready, type-safe)
  → Traditional API: Fastify (mature, plugin ecosystem)
  → Full-stack: Next.js API routes (ONLY for simple CRUD alongside frontend)
  → Complex backend: Separate Hono/Fastify service

Ruby team?
  → Rails (convention-over-config, fastest time-to-feature)

Python team?
  → API: FastAPI (async, type-safe, auto-docs)
  → Full-stack: Django (batteries-included, admin panel)

Go team?
  → Performance-critical: Go + Chi or Echo
  → gRPC services: Go + Connect

RULE: Next.js API routes are NOT a real backend.
Use them for BFF/proxy patterns only.
For business logic, use a separate service.
```

## Database Decision

```
DEFAULT: PostgreSQL. Always. Unless there's a specific reason not to.

Need document store?
  → Try PostgreSQL JSONB first (handles 90% of document use cases)
  → MongoDB ONLY if: schema-less by design AND no relational queries needed

Need key-value / cache?
  → Redis (session store, rate limiting, real-time counters)

Need full-text search?
  → PostgreSQL FTS first (handles most use cases)
  → Elasticsearch ONLY if: >1M documents AND complex faceted search

Need time-series?
  → TimescaleDB (PostgreSQL extension — same DB, new capabilities)

Prototype / side project?
  → SQLite (zero setup, file-based, surprisingly capable)
  → Migrate to PostgreSQL when you need concurrent writes
```

## ORM / Data Access

| Language | Recommended | Alternative | Avoid |
|----------|-------------|-------------|-------|
| TypeScript | Prisma (schema-first, migrations, type-safe) | Drizzle (code-first, lighter, SQL-like) | Raw queries everywhere |
| Ruby | ActiveRecord (Rails standard) | Sequel (for non-Rails) | — |
| Python | SQLAlchemy (explicit, powerful) | Django ORM (if using Django) | Raw SQL without parameterization |
| Go | sqlc (generated, type-safe, fast) | GORM (if team prefers ORM) | — |

## Testing Stack

| Framework | Unit | Component | Integration | E2E | Mock API |
|-----------|------|-----------|-------------|-----|----------|
| Next.js | Vitest | React Testing Library | Vitest + MSW | Playwright | MSW |
| Vite+React | Vitest | React Testing Library | Vitest + MSW | Playwright | MSW |
| Expo | Jest | React Testing Library | Jest + MSW | Maestro | MSW |
| Hono/Fastify | Vitest | — | Vitest + supertest | — | — |
| Rails | RSpec | — | RSpec + FactoryBot | Capybara | WebMock |
| FastAPI | pytest | — | pytest + httpx | Playwright | responses |
| Django | pytest | — | pytest + django test client | Playwright | responses |
| Go | testing | — | testcontainers-go | — | httptest |

## Hosting Decision

```
Containerized (recommended default)?
  → Simple: Fly.io (fast deploys, global, auto-scaling)
  → Fast iteration: Railway (git push deploy, managed Postgres)
  → Enterprise: AWS ECS / GCP Cloud Run

Serverless?
  → Next.js frontend: Vercel (zero-config, edge functions)
  → API: AWS Lambda + API Gateway (if already on AWS)
  → Edge: Cloudflare Workers (ultra-low latency, limited runtime)

Static?
  → Cloudflare Pages (free, fast, global CDN)
  → Vercel (if already using for dynamic parts)

Self-managed?
  → Local: Docker Compose
  → Production: Kubernetes (ONLY if team has k8s expertise)
```

## Bootstrap Commands

### Next.js (App Router)
```bash
npx create-next-app@latest {name} \
  --typescript --tailwind --eslint --app --src-dir \
  --import-alias "@/*" --use-npm
```

### Vite + React
```bash
npm create vite@latest {name} -- --template react-ts
cd {name} && npm install
# Add Tailwind manually:
npm install -D tailwindcss @tailwindcss/vite
```

### Expo (React Native)
```bash
npx create-expo-app@latest {name} --template blank-typescript
cd {name}
npx expo install nativewind tailwindcss react-native-reanimated
```

### Hono (Node.js API)
```bash
npm create hono@latest {name} -- --template nodejs
cd {name} && npm install
```

### Fastify (Node.js API)
```bash
mkdir {name} && cd {name}
npm init -y
npm install fastify @fastify/cors @fastify/helmet
npm install -D typescript @types/node tsx vitest
```

### Rails
```bash
rails new {name} \
  --database=postgresql --skip-jbuilder \
  --css=tailwind --javascript=esbuild
```

### FastAPI
```bash
mkdir {name} && cd {name}
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn sqlalchemy alembic
```

### Go
```bash
mkdir {name} && cd {name}
go mod init github.com/{org}/{name}
go get github.com/go-chi/chi/v5
```

## Constraint Modifiers

| Constraint | Override |
|-----------|---------|
| Existing team expertise | Prefer familiar stack over "optimal" — velocity matters more |
| Enterprise compliance | Prefer established frameworks (Rails, Django, Spring) over newer ones |
| Tight timeline (<4 weeks) | Prefer convention-over-config: Next.js, Rails, Django |
| High scale (>10K concurrent) | Plan connection pooling, read replicas, CDN from day one |
| Budget constraints | Prefer PaaS (Fly.io, Railway) over self-managed infra |
| Offline-first requirement | SQLite local + sync (Expo with expo-sqlite) |
| Multi-tenant SaaS | Row-level security in PostgreSQL from day one |

## Anti-Patterns

```
DON'T choose microservices for a greenfield project.
  → Start monolith. Extract services ONLY when team/scale boundaries emerge.

DON'T add a database you don't need yet.
  → SQLite or in-memory for prototypes. PostgreSQL when you need concurrent writes.

DON'T use Next.js API routes as a real backend.
  → They're fine for BFF/proxy. Business logic deserves its own service.

DON'T choose serverless if you need WebSockets or long-running processes.

DON'T pick a stack because it's trending on Hacker News.
  → Pick the stack your team can ship with fastest.

DON'T add Redis "for performance" on day one.
  → PostgreSQL handles more than you think. Add Redis when you measure a need.

DON'T skip TypeScript strict mode.
  → Every greenfield TypeScript project starts with strict: true. No exceptions.
```
