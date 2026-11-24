# Architecture

This document describes what is **implemented today (Day 1)** and the design the next days build toward.

## System overview

```
 Browser (React + TS)
   |  REST  /api/v1/...        JWT bearer token
   |  WS    /ws/...  (Day 2)   authenticated socket
   v
 FastAPI app
   api/routes   thin HTTP layer: parse, call a service, map errors to status codes
   services     business rules (registration, authentication; matchmaking and game logic on Day 2)
   models       SQLAlchemy ORM
   schemas      Pydantic request/response types
   core         settings, password hashing, JWT
   |
   v
 PostgreSQL 16  (schema managed by Alembic)
```

### Authority principle

The server owns game state. Clients send intents ("move e2 to e4"); the server authenticates the user, checks
they belong to the game and it is their turn, validates the move with a chess library, persists it, and only then
broadcasts the result. The frontend never decides legality or results.

## Backend layering

| Layer | Responsibility | Must not |
| --- | --- | --- |
| `api/routes` | HTTP concerns, status codes | contain business rules or SQL |
| `services` | use cases, transactions, domain errors | know about HTTP |
| `models` | persistence mapping and constraints | contain workflow logic |
| `core/security.py` | pure password and JWT helpers | touch the database |

Services raise domain errors (`DuplicateAccountError`, `InvalidCredentialsError`); routes translate them into 409/401.

## Authentication

- **Passwords:** Argon2id via `pwdlib`. Only the hash is stored.
- **Tokens:** HS256 JWTs with `sub`, `type`, `iat`, `exp`; all required on decode. The algorithm is pinned, so
  `alg: none` and wrong-secret tokens are rejected (covered by tests).
- **Login:** a dummy hash is verified when the email is unknown, and both failure modes return the identical
  401 body, so the endpoint does not reveal which emails are registered.
- **Protected routes:** `get_current_user` decodes the token and reloads the user, so deactivating an account
  invalidates its existing tokens immediately.
- **Frontend storage:** the token is kept in `localStorage`. Trade-off: readable by injected scripts (XSS). Mitigated by
  short token lifetime and no untrusted HTML rendering; revisited on Day 4's security review.

## Database schema

| Table | Purpose | Key constraints |
| --- | --- | --- |
| `users` | accounts | unique username and email; `is_active` |
| `games` | one row per match; UUID id | status/result enums; `time_control_seconds > 0`; `finished` status requires `finished_at` |
| `game_participants` | which user plays which color | unique `(game_id, color)` and `(game_id, user_id)`; FK cascade |
| `moves` | accepted moves in order | unique `(game_id, ply)`; stores UCI, SAN and resulting FEN |
| `player_statistics` | per-user win/loss/draw counters | one row per user; `wins + losses + draws <= games_played` |

Design notes:

- Enums use `VARCHAR` plus `CHECK` constraints (`native_enum=False`) rather than PostgreSQL enum types, which are
  awkward to alter in migrations.
- Constraints have deterministic names via a SQLAlchemy naming convention, so migrations are stable.
- Every model change must ship with a migration; `tests/test_schema.py::test_models_match_migrations` fails otherwise.
- Statistics are denormalised counters meant to be updated in the same transaction that finishes a game (Day 2).

## Frontend structure

```
src/lib/        config, token storage, API client (ApiError, bearer token, FastAPI error parsing)
src/components/ui/   reusable primitives (Button, Spinner)
src/features/        feature modules (status panel today; auth, dashboard, game from Day 3)
```

All network access goes through `lib/api/client.ts`, which centralises auth headers, error shape and network-failure
handling.

## Planned (not yet implemented)

- **Day 2:** python-chess validation, matchmaking queue, WebSocket protocol, server-authoritative clocks,
  persistence of games/moves/statistics.
- **Day 3:** routed UI, auth screens, dashboard, board, live game screen.
- **Day 4:** Docker, CI, deployment, end-to-end tests, full API/WebSocket reference docs.
