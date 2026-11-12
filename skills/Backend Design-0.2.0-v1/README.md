# Backend Design

A Claude Code plugin that teaches Claude to code like a senior backend engineer, not like a junior who memorized frameworks.

## Installation

If you use Claude Code's plugin marketplace, install via the UI. To install manually, place this directory under your Claude Code plugins location and enable it from settings.

### Hook requirements

The three Python hooks (`check_migration.py`, `check_backend_component.py`, `check_security.py`) need Python 3.8+ available as `python` on PATH. They warn-only, never block, and exit cleanly if something is off.

Platform notes:
- **Windows**: `python` is normally on PATH after the standard installer. `py` works too but `hooks.json` uses `python`. Tested working.
- **Linux**: most distros ship `python` as a symlink to `python3`. Works out of the box on Debian/Ubuntu (when `python-is-python3` is installed), Fedora, Arch. On a fresh distro that only ships `python3`, either install the alias package or edit `hooks/hooks.json` to call `python3`.
- **macOS**: Apple removed `python` (2.x) in macOS 12.3. Modern setups install Python 3 via `brew install python` (which provides `python3`), pyenv, or asdf. If `python` is not on PATH, either symlink it (`brew install python && ln -s $(which python3) /usr/local/bin/python`) or edit `hooks/hooks.json` to call `python3`.

If the hooks cannot run, nothing else in the plugin breaks: skills, agents, and commands work without them. You only lose the inline warnings at write time.

## Contributing

Contributions are welcome. The bar is "does this make Claude code more like a senior backend engineer?". See [CONTRIBUTING.md](CONTRIBUTING.md) for the style rules, what belongs (and what does not), and how to test changes.

## The Problem

Claude already knows the syntax. It knows REST, GraphQL, Redis, Postgres, Kafka, JWT, OAuth, SQL, ORMs. That part is fine.

What it does not have, by default, are the reflexes that distinguish a senior from a junior:

- Asking "at what load" before writing the first query.
- Listing failure modes and attack surfaces before writing the happy path.
- Treating idempotence as a property to design, not a bug to fix.
- Suspecting N+1 before running the code.
- Auditing its own diff for security holes before calling the change done.
- Modeling invariants in the schema, not in the service layer.
- Knowing that every migration is a potential incident.
- Knowing that observability is a feature, not a follow-up.
- Investigating before guessing when something breaks in prod.
- Testing what can break in interesting ways, ignoring the rest.

Backend Design adds those reflexes. It is opinionated, short, and applies to **every backend component**, not only HTTP endpoints: workers, consumers, CLIs, ETL, cron jobs, daemons, integrations.

## How It Works

The plugin installs thirteen skills, six agents, five commands, and three hooks. Together they make Claude:

1. Pause before writing code and run a 6-step workflow that includes load, security, and authorization.
2. Push schema invariants into the database, not the application.
3. Flag dangerous migrations before they ship.
4. Catch N+1 and unbounded queries before they reach production.
5. Treat idempotence and side effects as design, not cleanup.
6. Write structured logs, RED metrics, and real healthchecks by default.
7. Push back on premature complexity (the boring-tech principle).
8. Audit its own diff for the everyday security holes (IDOR, mass assignment, injection, secret leaks).
9. Design auth as two systems (authn vs authz), enforced at the right layers.
10. Size the work for the actual load instead of "optimizing" or "scaling" by reflex.
11. Investigate with a method when something breaks, instead of guessing.
12. Write tests that catch real regressions, not tests that decorate coverage.

## What Is In The Box

### Skills

- **`think-before-coding`**. The hub. Forces the 6-step workflow before any code: identify the context and load, model the data, list failure modes and attack surface, map authorization, decide idempotence, decide observability.
- **`data-modeling-discipline`**. Invariants in the schema (CHECK, FK, NOT NULL, UNIQUE), strict types, indexes from day one, no reflex soft delete.
- **`migration-safety`**. Catches the six dangerous patterns (NOT NULL without default, DROP without deprecation, one-shot rename, missing CONCURRENTLY, embedded backfill, CHECK without NOT VALID).
- **`query-discipline`**. EXPLAIN before merge, N+1 detection, cursor pagination by default, indexes that match the query.
- **`idempotency-and-side-effects`**. Idempotency keys, the outbox pattern, retries with backoff and jitter, no side effects inside DB transactions.
- **`error-handling-as-design`**. Errors are part of the contract: caller-vs-system split, stable error codes, no silent except, validate at the boundary.
- **`observability-by-default`**. Structured JSON logs, trace ID propagation, RED for endpoints, queue health for workers, real healthchecks.
- **`boring-by-default`**. Defends Postgres-and-a-monolith against the framework chase. Sessions over JWT for user auth. Adopt new tech only when the boring path is measurably out of room.
- **`performance-and-scaling`**. Forces "at what load" up front. Names the bottleneck axis (DB connections, query plan, allocations, lock contention, cache stampede). Pushes vertical scaling and indexes before distributed anything.
- **`security-discipline`**. The per-change reflex. Deny-by-default, mass assignment, injection across layers, secrets and PII in logs, error leaks, boring security headers.
- **`auth-and-authorization`**. Authn vs authz as two systems. Enforcement layers (middleware, service, RLS). RBAC / ABAC / ReBAC choice. OAuth2 sanity. Multi-tenancy.
- **`debugging-discipline`**. The investigation method when something breaks. Active incident vs stable bug, reproduce/bisect/measure, one hypothesis at a time, document as you go.
- **`testing-with-discernment`**. Test what can break in interesting ways. Integration over mocks for data-layer code. Tests that lie. Bug-first regression tests. Speed and determinism.

### Agents

- **`schema-reviewer`**. Reviews a CREATE TABLE / migration / model file. Returns a tight, severity-ordered list of fixes.
- **`component-architect`**. Designs a backend component (any type) by running the 6-step workflow and producing a blueprint.
- **`incident-thinker`**. Lists realistic incident scenarios for a component, with detection and recovery for each. Useful before shipping.
- **`boring-tech-advisor`**. Challenges proposed new tech with four questions. Forces a defense or proposes the boring alternative.
- **`security-reviewer`**. Reviews a diff, file, or component with security goggles. Returns blocking / should-fix / worth-considering, with file:line references.
- **`incident-investigator`**. Drives an active investigation when something is broken in prod or staging. Different from incident-thinker (which is design-time); this one walks the user through symptom definition, hypothesis testing, and root cause.

### Commands

- **`/backend-design:design`**. Drive a design session for any backend component (endpoint, worker, CLI, consumer, cron, integration). Runs the 6-step workflow, then hands off to the architect.
- **`/backend-design:review-migration`**. Pass a migration through the migration-safety checklist. Flags risks, proposes safer patterns.
- **`/backend-design:audit`**. Audit an existing component against senior discipline. Returns gaps in invariants, auth, errors, idempotence, queries, observability.
- **`/backend-design:hunt-n-plus-one`**. Scan code for N+1 patterns across ORMs and raw SQL. Returns findings ranked by confidence with concrete fixes.
- **`/backend-design:explain-this-query`**. Predict the execution plan for a query, flag missing indexes and unbounded sorts, recommend the EXPLAIN step.

### Hooks

- **`check_migration.py`**. Pre-write hook on migration files. Warns when a write would introduce a dangerous pattern.
- **`check_backend_component.py`**. Pre-write hook on backend component files. Detects the component type (endpoint / worker / cron / integration) and warns when senior reflexes are missing: silent except, no validation, no idempotency, HTTP call without timeout, and so on.
- **`check_security.py`**. Pre-write hook for security horrors. Flags string-concat SQL, hard-coded secrets, sensitive fields in logs, disabled TLS verification, `shell=True` with input, weak crypto, tokens in URLs, CORS wildcard with credentials.

All hooks warn, none of them block.

## Before And After

### Before, without the plugin

```
User: "Add an endpoint to charge a customer for an order."

Claude writes:
- POST /orders/:id/charge
- Reads order, calls Stripe inline, marks order paid.
- No idempotency key. No retry policy. No outbox.
- Stripe call inside the DB transaction.
- A try/except around the whole thing logs "charge failed".
```

### After, with the plugin

```
User: "Add an endpoint to charge a customer for an order."

Claude:
1. Classifies: sync HTTP endpoint at expected ~10 req/s peak,
   latency budget hundreds of ms, strict failure model (money).
2. Models the data: order.status in a fixed set, FK to customer,
   invariant: charged_at IS NULL OR amount > 0.
3. Lists failures AND attack surface: order already paid (409),
   payment method missing (422), Stripe timeout (5xx + retry-safe),
   Stripe 4xx (deterministic). IDOR on the order id, mass assignment
   on the body, idempotency key in the header.
4. Authorization: requesting user owns the order OR is admin;
   enforced at the data layer plus DB-level tenant scope (RLS).
5. Idempotency: client sends Idempotency-Key, server stores
   (key, request_hash, response). Outbox row inserted in the same
   transaction as the order update. Background worker calls Stripe
   with the outbox row ID as the Stripe idempotency key.
6. Observability: log "order.charge.requested", "order.charge.completed",
   "order.charge.failed" with trace_id and order_id. RED on the endpoint,
   call rate + error rate per Stripe status on the integration.
```

### Before, without the plugin

```
User: "The API has been slow this morning."

Claude says: "Let me add some caching and increase the connection pool."
```

### After, with the plugin

```
Claude: "Before any change, four questions:
  When did it start? Same hour as the 09:12 deploy, or earlier?
  Who sees it? All routes or one? All tenants or one?
  What fraction? 100% or intermittent?
  What is the exact behavior? P50 up, p99 up, or just timeouts?

Then: where to look. The deploy diff if the window matches.
The slow query log on the primary. Postgres pg_stat_activity
for lock waits. APM trace for one slow request.

One hypothesis at a time. Predict, look, judge. No fix
without a reproduction or a clear measured cause."
```

### Before, without the plugin

```
User: "Add a NOT NULL column 'currency' to invoices."

Claude writes a single migration:
  ALTER TABLE invoices ADD COLUMN currency text NOT NULL DEFAULT 'USD';
```

### After, with the plugin

```
Claude flags: on a large invoices table this works in Postgres 11+
thanks to virtual defaults, but if the default is computed or the
column needs a non-null value derived from data, the safe form is:

  Migration A: ALTER TABLE invoices ADD COLUMN currency text;
  Backfill script (separate, batched, restartable): set currency from
    customer.country.
  Migration B: ALTER TABLE invoices ALTER COLUMN currency SET NOT NULL;

And the PR description names the rollback plan.
```

## Companion

This plugin is the backend counterpart to [Frontend Design](https://claude.com/plugins/frontend-design). One teaches Claude to write distinctive interfaces. This one teaches it to write durable services.

## License

MIT. See LICENSE.
