# REST API

Base path: `/api/v1`. Authenticated endpoints need `Authorization: Bearer <token>`. Interactive schema: `/docs` on a
running server. Live gameplay uses the [WebSocket protocol](WEBSOCKET_PROTOCOL.md).

## Health (no prefix, no auth)

| Method | Path | Result |
| --- | --- | --- |
| GET | `/health` | 200, process is up |
| GET | `/health/ready` | 200 if the database is reachable, else 503 |

## Authentication and users

| Method | Path | Auth | Success | Errors |
| --- | --- | --- | --- | --- |
| POST | `/auth/register` | no | 201 user | 409 taken, 422 invalid |
| POST | `/auth/login` | no | 200 `{access_token, token_type}` | 401, 422 |
| GET | `/users/me` | yes | 200 your account | 401 |
| GET | `/users/me/statistics` | yes | 200 `{games_played, wins, losses, draws}` | 401 |
| GET | `/users/{username}` | yes | 200 public profile and statistics (no email) | 401, 404 |

## Matchmaking

| Method | Path | Body | Success | Errors |
| --- | --- | --- | --- | --- |
| GET | `/matchmaking/time-controls` | | 200 list (3, 5, 10 minutes); public | |
| POST | `/matchmaking` | `{time_control_seconds, increment_seconds?}` | 200 `queued` or `matched` | 409 already searching or in a game, 422 unsupported |
| GET | `/matchmaking/status` | | 200 `idle`, `queued` or `matched` (with `game_id`, `color`) | |
| DELETE | `/matchmaking` | | 200 `idle`, or `matched` if pairing happened first | |

**Client contract:** while searching, poll `/matchmaking/status` every 2–3 s. Polling is the heartbeat: an entry not
refreshed for 15 s is treated as abandoned and will not be paired.

**Creating games:** matchmaking is the only way a game is created. There is intentionally no endpoint that can put
another user into a game they did not ask for.

## Games (players of the game only)

| Method | Path | Success | Errors |
| --- | --- | --- | --- |
| GET | `/games/active` | 200 your unfinished game state, or `null` | |
| GET | `/games/history?limit=20&offset=0` | 200 `{items, total, limit, offset}`; finished games, newest first; `limit` 1–100 | 422 |
| GET | `/games/{id}` | 200 full state, including moves | 403, 404 |
| GET | `/games/{id}/result` | 200 `{status, result, result_reason, finished_at}` | 403, 404 |
| POST | `/games/{id}/resign` | 200 final state; connected players are notified | 403, 404, 409 already over |

Moves are accepted only over the WebSocket. All endpoints return 401 without a valid token.
