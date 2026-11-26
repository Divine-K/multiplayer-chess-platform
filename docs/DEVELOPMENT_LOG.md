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

- **Date:** 2026-11-26
- **Objectives:** Visual design system, landing page, authentication screens, dashboard, interactive board, live
  multiplayer over WebSockets, match history, animation, frontend tests, and verification with two browser sessions.

### Features implemented

- **Design system:** dark theme with one brass accent, Inter and Fraunces (self-hosted), shared UI primitives, toasts,
  skeletons and accessible dialogs. The interface is branded "Tempo". Animations respect reduced-motion settings.
- **Pages:** landing (hero, features, how it works, footer), sign-in, sign-up, dashboard, match history, live game,
  not-found.
- **Sessions:** route guards that return you to the page you wanted, expired-token handling, retry when the server is
  unreachable, and sign-in changes followed across tabs.
- **Matchmaking:** time control choice, search animation, cancel, resume after reload, a search that survives
  navigation, and leaving the queue on sign-out.
- **Board:** own component with original SVG pieces; click, drag and keyboard input; highlighting for selection, legal
  moves, last move, check and pending moves; promotion picker.
- **Game screen:** player bars with colour, clock, captured pieces and material lead, opponent presence and record,
  move list, draw offers, resignation confirmation, result dialog, reconnect and "opened elsewhere" states.

The backend was not changed.

### Files created or modified

New: `frontend/src/features/{auth,dashboard,game,history,landing,matchmaking}/`, `features/NotFoundPage.tsx`,
`components/layout/`, new `components/ui/` primitives, `lib/{brand,format,useAsync}.ts`, `lib/api/{games,types}.ts`,
`src/test/` helpers, `frontend/e2e/`, `frontend/playwright.config.ts`. Modified: `App.tsx`, `main.tsx`, `index.css`,
`index.html`, favicon, API client, token storage, Vite and TypeScript config, `.gitignore`, docs. Removed the Day 1
backend-status panel and its tests.

### Tests executed

| Suite | Result |
| --- | --- |
| Frontend Vitest (`npm test`), 5 consecutive runs at 113 tests, then final run | **115 passed** |
| Frontend `tsc -b --force`, oxlint, production build | clean, succeeds |
| Playwright against the real API and PostgreSQL (`--repeat-each=3`) | **18 of 18 passed** (6 scenarios, 3 runs) |
| Backend `pytest` (unchanged) | **182 passed** |
| Backend ruff, `mypy --no-incremental` | clean |

Vitest per file: game screen 19, socket 18, board 17, auth and landing 15, matchmaking 10, formatting 9, API client 9,
reducer 6, history 5, board helpers 5, config 2.

### Integration results (two isolated browser sessions in Google Chrome)

Covered by `frontend/e2e/`:

| Requirement | Observed |
| --- | --- |
| Both players join the same game and see the same board | same game URL, identical 32-piece position |
| A valid move updates both | yes, including a drag-and-drop move, captures and a promotion |
| An illegal move is rejected | a move rewritten in transit to `e2e5` was refused by the server; neither board changed |
| Turns switch | yes; the player not on turn cannot select a piece |
| Clocks are consistent | both sessions agreed within 1 s |
| Completion reaches both | checkmate, resignation and agreed draw; history and statistics updated |
| Refresh and reconnect | position and moves restored; the opponent saw the disconnect and the return |
| Second tab for one player | newest connection wins; the older one can take it back |
| Layout | no sideways scrolling at 320, 375, 768 and 1366 px; board square and on screen, clocks visible |

**Run once with a temporary script (not in the repository):** the API process was stopped mid-game and restarted
about 6 s later. Both sessions reconnected without a reload with the position intact, black's clock had kept running
(2:53 of 3:00), and play continued. White then let the clock expire: after **180.2 s** both screens showed the result
"on time" and white's clock read 0:00.0, with no page errors.

The screens were also reviewed from screenshots at desktop, tablet and phone sizes. All throwaway accounts and their
games were deleted from the development database afterwards.

### Problems encountered

- **Sideways scroll on phones** (23 px on the game screen), found in screenshot review: the grid had no column size
  below the desktop breakpoint. Fixed, and now covered by a browser test.
- **Stale "game in progress" banner:** found in code review. If that game ended or was cancelled while the dashboard
  was open, Play stayed disabled until a reload. The dashboard now re-checks it; covered by a test.
- **Captured black pieces** were nearly invisible on the dark background; given a light halo.
- **Two test timing faults:** assertions ran before an exit animation and a redirect had finished.
- **Preview tool:** it could not start the API on port 8000, so the API was run directly from the shell.

### Known limitations

- Only Google Chrome was tested. Firefox, Safari and real touch devices have not been.
- Finished games show the final position only; you cannot step back through earlier moves.
- There is no site-wide "online" indicator, because the backend tracks presence only inside a game.
- A search left in a long-hidden tab can expire if the browser throttles its timers; the player is told.
- Sign-in is shared by all tabs in one browser profile.
- Displayed clocks can lag the server by the network delay; the server's clock decides.
- The token is still kept in `localStorage` (Day 4 security review).
- The JavaScript is one bundle (about 154 kB gzipped), not yet split by route (Day 4 performance review).

### GitHub commits (Day 3, in order)

1. `feat: add design system and UI primitives`
2. `feat: build interactive chessboard`
3. `feat: implement authentication screens`
4. `feat: add player dashboard, matchmaking and match history`
5. `feat: integrate real-time multiplayer gameplay`
6. `feat: build landing page and connect the application`
7. `test: add frontend integration tests`
8. `test: add two-player browser tests`
9. `docs: document the web app and Day 3 results`

Commits 1 to 6 split one working tree by layer. Each commit up to 8 was checked with a cold type check; the full
test and browser results above are for the final state.

### Next steps: Day 4 objectives

Full-system testing across many match scenarios, bug fixes, performance and security review, Docker and Compose,
GitHub Actions, deployment, README with screenshots, and the remaining documentation.

## Day 4

Not started.
