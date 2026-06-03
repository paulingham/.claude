# Module Boundaries Protocol

The harness defaults to a **modular monolith**: in-process boundaries first, new services only when a forcing function is named. This file is the single source of truth for what a module is, what contract it exposes, how it is tested at the seam, and the exact forcing-function criteria that justify promoting a module to a service.

When you are considering "splitting X out", read this file first. If no forcing function applies, `X` is a module, not a service.

## What a Module Is

- A **directory + namespace/package** with a single public entry point (port/interface)
- No file outside that directory imports from its internals — only from its public surface
- The module owns its internal types, helpers, and state; callers never reach past the port
- Reversible by construction: moving/renaming the directory is a refactor, not a migration

Contrast with a service: a service adds a process boundary, a network hop, a separate deploy, and a contract encoded in OpenAPI/Protobuf/events. Those are expensive and hard to reverse. A module's seam is a function call; a service's seam is a failure domain.

## Module Contract Artifacts

Every module ships two required artifacts and may ship two optional ones:

| Artifact | Required | Purpose |
|----------|----------|---------|
| `interface.{ts,rb,py,go}` (or language equivalent) | Yes | The public port — types + function/method signatures callers rely on |
| `README.md` | Yes | Responsibilities, invariants, what this module owns and does NOT own |
| `types.{ext}` | Optional | When the surface area warrants splitting types out of `interface.{ext}` |
| `events.{ext}` | Optional | When the module emits domain events that other modules subscribe to |

Small modules ship a single `interface.{ext}`. Larger modules split contract into `interface.{ext}` + `types.{ext}` (+ `events.{ext}` if event-driven). The split is a size threshold, not a policy — if `interface.{ext}` grows past what a reader can hold in their head, split.

## Testing at the Seam

Every module has at least one test that exercises it **only through its public port**, with all external collaborators injected (DIP at the module boundary, not just the class boundary).

- The seam test imports from the module's public entry point — never from internals
- External dependencies (SDKs, DB clients, HTTP clients, other modules) are injected, not reached for globally
- Internal tests may still use white-box access to verify unit behavior; the seam test proves the contract

If the seam is not testable, the module isn't ready to be a module yet — the boundary is not where you think it is.

## Forcing-Function List (FF1–FF5) — Canonical

A request is allowed to route to `/service-extraction` or `/microservices-scaffold` only when at least one of these forcing functions is present. This list is canonical; other documents link to it rather than restating it.

- **FF1 — Independent scaling with divergent compute profile**: the module's CPU/memory/IO shape is materially different from the host (e.g. GPU inference, long-running batch, heavy egress) AND cost or latency is measurably worse co-located.
- **FF2 — Conway's Law at scale**: a team of 30-50+ engineers where the module has a dedicated squad that needs its own release cadence.
- **FF3 — Fault isolation**: blast radius must not cross a process boundary (e.g. a crashy third-party SDK, a memory-unsafe dependency, payment processing where a panic in the host must not take down checkout).
- **FF4 — Regulatory/data residency**: data must physically live in a different jurisdiction, VPC, or compliance boundary (PCI, HIPAA, GDPR region isolation).
- **FF5 — Polyglot runtime**: the module genuinely needs a runtime the host cannot host (Python ML in a Ruby monolith, a Rust hot path, a JVM library with no port in the host language).

**Absence of all five = modular monolith is correct.** "We'll want to split this one day" is not a forcing function; it is a refactor you can do later, cheaply, because the module has a clean port.

## Decision Checklist

Before extracting to a service:

1. Name the forcing function explicitly. Write it down: "FF{N}: {reason tied to measurable signal}".
2. If you cannot name one — stop. This is a module, not a service. Use `/harness:module-extraction`.
3. If you named one — continue to `/service-extraction` or `/microservices-scaffold`. The pipeline will re-check at Step 0; vague rationale fails that check.

The checklist is deliberately short: the canonical FF list does the filtering, not the checklist.

## Per-Language Seam Enforcement

Language-specific lint/tool setup for enforcing module boundaries (ESLint `no-restricted-imports`, Ruby `packwerk`, Python `import-linter`, Go `internal/` packages) lives in `skills/module-extraction/SKILL.md`. This file is language-agnostic; the skill file carries the per-language rule table.

## Relationship to Multi-Repo Protocol

`protocols/multi-repo-protocol.md` applies only to projects that are already multi-repo. New projects default to the module boundaries defined here. Adopting multi-repo is a forward move from a modular monolith when a forcing function appears — not the starting point.
