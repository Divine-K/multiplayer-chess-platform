# Development Progress

## Day 1

- **Date:** 2026-11-24
- **Objectives:** Environment setup, architecture, database, authentication foundation, frontend skeleton, docs.

### Features implemented

- Git repository and private GitHub repo `Divine-K/multiplayer-chess-platform`.
- Backend: FastAPI app factory, typed settings (`pydantic-settings`; secrets have no defaults), CORS, liveness
  (`/health`) and readiness (`/health/ready`, checks the database) probes.
- Database: SQLAlchemy 2.0 models for users, games, game participants, moves and player statistics with constraints and
  indexes; Alembic configured; initial migration `0001_initial_schema`.
- Authentication: registration, login, Argon2id hashing, JWT access tokens, protected `GET /api/v1/users/me`.
- Frontend: Vite + React 19 + TypeScript, Tailwind v4 design tokens, Framer Motion/Lucide/React Router installed,
  typed API client, `Button`/`Spinner` primitives, live backend-status panel.
- Docs: README, `docs/ARCHITECTURE.md`, this log.

### Files created or modified

`backend/app/{core,db,models,schemas,services,api}`, `backend/migrations/`, `backend/tests/`,
`backend/{requirements*.txt,pyproject.toml,pytest.ini,alembic.ini,.env.example}`;
`frontend/src/{lib,components,features,test}`, `frontend/{package.json,vite.config.ts,tsconfig*.json,index.html}`;
`.gitignore`, `.env.example`, `README.md`, `docs/`.

### Tests executed

| Suite | Command | Result |
| --- | --- | --- |
| Backend (real PostgreSQL) | `pytest` | **35 passed** |
| Backend lint/format/types | `ruff check`, `ruff format --check`, `mypy app tests` (strict) | clean |
| Migration drift | `alembic check` | no drift |
| Frontend unit/component | `npm test` (Vitest) | **13 passed** |
| Frontend static | `npm run lint`, `npm run typecheck` | clean |
| Frontend build | `npm run build` | succeeds |

Manual verification against live servers: health/readiness, register, login, authenticated and unauthenticated
`/users/me` (200/401), CORS preflight (allowed origin accepted, unknown origin rejected), and the React app in a
browser showing "API and database are healthy" against the real backend and database.

### GitHub commits

Commit hashes are in `git log`. Messages, in order:

1. `chore: initialize project structure`
2. `feat: establish PostgreSQL database architecture`
3. `feat: implement authentication foundation and health checks`
4. `chore: configure frontend environment`
5. `feat: add frontend API layer, UI primitives and backend status panel`
6. `docs: add initial architecture and setup documentation`

### Problems encountered

- **Docker daemon not running** and **PostgreSQL not installed** on the machine. Installed PostgreSQL 16 via Homebrew
  for local development. Docker configuration is Day 4 scope, so it is not yet verified.
- **Model/migration drift** found by `alembic check` (constraint names, timezone-aware columns, redundant
  unique+index on `users`). Fixed; a test now guards against recurrence.
- **ORM delete bug:** deleting a user tried to null participant rows instead of relying on `ON DELETE CASCADE`.
  Caught by a test; fixed with `passive_deletes=True`.
- **CORS is origin-exact:** the frontend works at `localhost:5173` but correctly fails at `127.0.0.1:5173`.
  Documented in the README.
- Known warning: Starlette reports its `TestClient` HTTP dependency as deprecated in favour of `httpx2`; harmless for now.

### Known limitations

- No refresh tokens or logout endpoint (tokens simply expire).
- No rate limiting on login yet.
- Backend tests require a local PostgreSQL `*_test` database; CI provisioning is Day 4.

### Next steps: Day 2 objectives

Chess engine (python-chess), matchmaking queue, WebSocket protocol and authentication, server-authoritative clocks,
REST endpoints (profiles, games, history, statistics), transactional persistence, and backend/WebSocket tests.

## Day 2

Not started.

## Day 3

Not started.

## Day 4

Not started.
