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

- **Date:** 2026-11-25
- **Objectives:** Chess engine, matchmaking, WebSockets, server clocks, REST APIs, persistence, backend tests.

### Features implemented

- **Engine:** authoritative wrapper over python-chess 1.11.2 (castling, en passant, promotion, check, checkmate,
  stalemate, insufficient material, threefold repetition, fifty-move rule).
- **Clocks:** persisted, server-derived, increment-capable; 250 ms sweeper for flag fall and never-started games.
- **Persistence:** migration `0002_gameplay_and_matchmaking`; each command is one row-locked transaction covering
  move, clocks, result and statistics.
- **Matchmaking:** database FIFO queue, random colors, heartbeat expiry, cancel, advisory-lock concurrency control,
  database-enforced one active game per player.
- **WebSockets:** first-message JWT auth, origin check, participant authorization, typed protocol, size/rate/idle
  limits, newest-connection-wins, disconnect notices, reconnection with full state, periodic clock sync.
- **REST:** matchmaking, game state, active game, result, resign, history, own statistics, public profiles.
- **Docs:** `docs/API.md`, `docs/WEBSOCKET_PROTOCOL.md`; architecture and README updated.

### Architecture decisions

| Decision | Reason |
| --- | --- |
| Clock stored as remaining time + turn start, never ticking | survives restarts, deterministic, client-proof |
| Row lock for data, per-game asyncio lock around commit-then-broadcast | correctness and event ordering are separate problems |
| Advisory lock for pairing, not `SKIP LOCKED` | with `SKIP LOCKED`, two simultaneous joiners can both find nobody |
| Polling for matchmaking status | simple, and doubles as a liveness heartbeat |
| Token in first socket message, not the URL | keeps tokens out of access logs |
| Threefold and fifty-move draws are automatic | no extra claim protocol |
| Game starts when both sockets connect; aborted after 60 s otherwise | nobody loses time before arriving, and no one stays stuck |
| Games are created only by matchmaking | no way to force another user into a game |

### Files created or modified

New: `backend/app/chess_core/`, `backend/app/realtime/`, `backend/app/services/{game_service,game_queries,
matchmaking_service,time_controls}.py`, `backend/app/api/routes/{games,matchmaking}.py`,
`backend/app/schemas/{game,matchmaking}.py`, `backend/app/models/matchmaking.py`, `backend/app/core/time.py`,
`backend/migrations/versions/0002_gameplay_and_matchmaking.py`, seven new test modules and two helper modules.
Modified: models, errors, config, `main.py`, user routes, requirements, docs.

### Tests executed

| Suite | Result |
| --- | --- |
| Backend `pytest` (real PostgreSQL) | **182 passed** |
| Ruff lint and format, mypy strict | clean |
| `alembic check`, and 0002 downgrade/upgrade round trip | no drift, succeeds |
| Frontend Vitest (unchanged since Day 1) | 13 passed |

Per file: engine 35, WebSocket 43, REST gameplay 22, game service 22, auth 18, matchmaking 15, clock 8, schema 8,
security 8, health 2, sweeper 1.

The suite passed six consecutive times after the disconnect fix (181 tests at that point), before the sweeper test was
added.

**Mutation checks on concurrency tests:** with the matchmaking advisory lock removed, all 4 concurrent matchmaking
tests failed. With the game row lock removed, the racing resign/timeout test failed. The duplicate-move test still
passed without the row lock, so it does not reliably detect a missing lock (the unique `(game_id, ply)` constraint
remains a backstop).

**Live run against a real uvicorn server** (two independent network clients, 13 checks, all passed): match and start,
castling sync, out-of-turn rejection, disconnect notice, reconnect with 7 moves, server restart mid-game with the
clock still running, resignation, persisted history and statistics, and a **real 3-minute flag fall at 180.16 s** with
35 periodic clock syncs received by white. The server log had no errors. This was a temporary script, not part of the
repository, and covered 2 games.

### Problems encountered

- **Lost disconnect notice:** Starlette's test client cancels the server task right after disconnecting, which killed
  the cleanup broadcast. Cleanup is now shielded from cancellation; also verified on a real server.
- **Sweeper robustness:** found in review that one failing game would block the rest of a sweep pass. Fixed and tested.
- **Stale mypy cache:** a fresh-clone check showed that incremental mypy runs had reported success while a cold run
  failed on an unneeded `type: ignore` in `realtime/protocol.py`. Removed it; type checks are now verified with
  `mypy --no-incremental`.

### Known limitations

- Single API instance only (in-memory connection rooms).
- No UI for gameplay yet. Two real **browser** sessions are verified on Day 3.
- Socket tokens are not re-checked after connection; no REST rate limiting (Day 4 security review).
- Draw offers can be repeated after a decline (bounded only by the message rate limit).
- No rating system; matchmaking is first-come, first-served. No lag compensation.
- The offered time controls have no increment, although the clock supports it.

### GitHub commits (Day 2, in order)

1. `feat: extend schema for gameplay and matchmaking`
2. `feat: implement chess game engine`
3. `feat: add server-authoritative chess clock`
4. `feat: add transactional game service with persistence and statistics`
5. `feat: implement multiplayer matchmaking`
6. `feat: add WebSocket game synchronization and server-enforced timeouts`
7. `feat: add REST APIs for matchmaking, games and player profiles`
8. `test: add REST and WebSocket integration tests`
9. `fix: isolate per-game failures in the timeout sweeper`
10. `docs: document the API, WebSocket protocol and Day 2 progress`
11. `fix: remove unneeded type ignore surfaced by a cold mypy run`

### Next steps: Day 3 objectives

Visual design system, landing page, login and registration, dashboard with real data, interactive board, live game
screen over the WebSocket protocol, match history, animations, frontend tests, and verification with two separate
browser sessions.

## Day 3

Not started.

## Day 4

Not started.
