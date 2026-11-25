# Multiplayer Chess Platform

Full-stack real-time multiplayer chess platform built with FastAPI, React, TypeScript, WebSockets, and PostgreSQL.

> **Status: Day 2 of 4 complete.** The backend is functional: chess rules, matchmaking, real-time WebSocket play,
> server clocks, persistence, history and statistics. **There is no playable UI yet**; the frontend is built on Day 3.
> See [docs/DEVELOPMENT_LOG.md](docs/DEVELOPMENT_LOG.md).

## Goals

Users register, find an opponent, play real-time chess, and review past games and statistics. The backend is the
single source of truth for game state: the browser only sends move *intents*, and the server validates them
before anything changes.

## Technology stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, Framer Motion, Lucide, React Router |
| Backend | Python, FastAPI, Pydantic v2, WebSockets, python-chess |
| Database | PostgreSQL 16, SQLAlchemy 2.0, Alembic |
| Auth | JWT access tokens, Argon2id password hashing |
| Testing | Pytest, Vitest, React Testing Library (Playwright planned for Day 4) |
| Tooling | Ruff, mypy (strict), oxlint, Git/GitHub (Docker and CI planned for Day 4) |

## Repository layout

```
backend/    FastAPI app (api/ routes, services/ business logic, realtime/ WebSockets,
            chess_core/ rules and clock, models/ ORM, schemas/ API types)
  migrations/   Alembic migrations
  tests/        Pytest suite (runs against a real PostgreSQL database)
frontend/   React + TypeScript app (lib/ API client, components/ UI, features/ feature modules)
docs/       Architecture notes and the development log
```

## Local setup

Prerequisites: Python 3.12+, Node.js 20+, PostgreSQL 16+.

### 1. Database

Create a role and two databases (one for development, one for tests):

```sql
CREATE ROLE chess WITH LOGIN PASSWORD 'choose-a-password';
CREATE DATABASE chess_dev  OWNER chess;
CREATE DATABASE chess_test OWNER chess;
```

### 2. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # then edit DATABASE_URL and JWT_SECRET_KEY
alembic upgrade head          # create the schema
uvicorn app.main:app --reload # http://localhost:8000  (API docs at /docs)
```

Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local    # optional; defaults to http://localhost:8000
npm run dev                   # http://localhost:5173
```

Open the app at **`http://localhost:5173`** (not `127.0.0.1`): the backend's CORS allow-list is origin-exact.

## Environment variables

| Variable | Where | Description |
| --- | --- | --- |
| `DATABASE_URL` | backend | SQLAlchemy URL, e.g. `postgresql+psycopg://chess:pw@localhost:5432/chess_dev`. Required. |
| `JWT_SECRET_KEY` | backend | Token signing secret, at least 32 characters. Required. |
| `ENVIRONMENT` | backend | `development`, `test` or `production`. Production rejects placeholder secrets. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | backend | Access token lifetime. Default 60. |
| `CORS_ORIGINS` | backend | JSON list of allowed browser origins. Default `["http://localhost:5173"]`. |
| `MATCHMAKING_STALE_SECONDS` | backend | Queue entry expiry without a status poll. Default 15. |
| `GAME_START_TIMEOUT_SECONDS` | backend | Abort a paired game that never starts. Default 60. |
| `WS_IDLE_TIMEOUT_SECONDS` | backend | Close silent sockets. Default 60. Other `WS_*` limits are in `app/core/config.py`. |
| `VITE_API_BASE_URL` | frontend | Backend origin. Default `http://localhost:8000`. |

Secrets live only in untracked files (`backend/.env`, `backend/.env.test`, `frontend/.env.local`). They are
git-ignored; only `.env.example` templates are committed.

## Database

Schema changes go through Alembic migrations, never manual edits.

```bash
alembic upgrade head                       # apply
alembic downgrade base                     # roll everything back
alembic revision --autogenerate -m "msg"   # create a new migration after changing models
alembic check                              # fails if models and migrations have drifted
```

Tables: `users`, `games`, `game_participants`, `moves`, `player_statistics`, `matchmaking_queue`. Integrity rules (one player per
color per game, unique ply numbers, non-negative counters, valid enum values) are enforced by database
constraints, not just application code. Details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Backend features

- Server-validated chess: castling, en passant, promotion, check, checkmate, stalemate, insufficient material,
  threefold repetition and the fifty-move rule.
- Matchmaking for 3, 5 and 10 minute games, safe under concurrent requests.
- Real-time play over authenticated WebSockets, with reconnection.
- Server-authoritative clocks that keep running through disconnects and server restarts.
- Resignation, draw offers, match history and win/loss/draw statistics.

Reference: [REST API](docs/API.md) · [WebSocket protocol](docs/WEBSOCKET_PROTOCOL.md) ·
[Architecture](docs/ARCHITECTURE.md). Run **one** API process (see the scaling note in the protocol doc).

## Testing

```bash
# Backend: needs a *_test database; create backend/.env.test with its DATABASE_URL
cd backend && pytest
ruff check . && ruff format --check . && mypy app tests

# Frontend
cd frontend && npm test && npm run lint && npm run typecheck && npm run build
```

The backend suite refuses to run unless the database name ends in `_test`, so it can never wipe development data.

## Roadmap

- **Day 3:** landing page, auth screens, dashboard, interactive board, live multiplayer UI.
- **Day 4:** end-to-end testing, Docker, CI, deployment, final documentation.
