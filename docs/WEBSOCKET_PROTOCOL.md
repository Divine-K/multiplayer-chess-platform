# WebSocket protocol

Endpoint: `ws(s)://<api-host>/ws/games/{game_id}` (one socket per player per game).

## Envelope

Every message, in both directions:

```json
{ "type": "move", "game_id": "6f1c…", "payload": { "from": "e2", "to": "e4" } }
```

`game_id` is optional from clients. If present it must match the socket's game. Server messages always include it.
Unknown fields are rejected.

## Connecting

1. Open the socket. Browser requests must come from an origin in `CORS_ORIGINS` (CORS itself does not cover
   WebSockets, so the server checks `Origin`).
2. Within 10 s, send `{"type":"auth","payload":{"token":"<JWT>"}}`. The token is deliberately not in the URL, so it
   never appears in access logs.
3. The server verifies the token, the account, and that you are a player in this game, then replies `connected`.
4. When **both** players are connected, the game becomes active, white's clock starts, and both receive `game_started`.
   A game that has not started 60 s after pairing is aborted (no statistics recorded).

## Client messages

| type | payload | notes |
| --- | --- | --- |
| `auth` | `{token}` | first message only |
| `move` | `{from, to, promotion?}` | squares like `e2`; `promotion` is `q`, `r`, `b` or `n` |
| `resign` | `{}` | on a game that has not started, aborts it |
| `offer_draw` | `{}` | offering while the opponent's offer is pending accepts it |
| `accept_draw` / `decline_draw` | `{}` | only for the opponent's offer |
| `sync` | `{}` | request the full current state |
| `ping` | `{}` | heartbeat; answered with `pong` |

## Server events

| type | payload | sent to |
| --- | --- | --- |
| `connected` | `{color, opponent_connected, state}` | you |
| `player_connected` / `player_disconnected` | `{color}` | opponent |
| `game_started` | `{state}` | both |
| `move_accepted` | `{move: {ply, uci, san, color}, state}` | both |
| `turn_changed` | `{turn, ply, version}` | both (only while the game continues) |
| `move_rejected` | `{code, message, state}` | sender only |
| `clock_updated` | `{clocks, version, server_time}` | both, about every 5 s |
| `draw_offered` | `{by, state}` | both |
| `draw_declined` | `{state}` | both |
| `game_finished` | `{status, result, result_reason, state}` | both |
| `state` | `{state}` | you (reply to `sync`) |
| `pong` | `{}` | you |
| `closing` | `{code}` | you, immediately before the server closes your socket |
| `error` | `{code, message}` | you |

A move that ends the game produces `move_accepted` followed by `game_finished`. An opponent's move silently clears a
pending draw offer (`state.draw_offered_by` becomes `null`).

### `move_rejected` codes

`illegal_move`, `invalid_move_format`, `promotion_required`, `not_your_turn`, `game_not_active`, `flag_fallen`.

`flag_fallen` means your time expired before the move arrived. The move is discarded and `game_finished` is sent to
both players first.

### `error` codes

`invalid_message`, `invalid_draw_action`, `game_not_active`, `internal_error`.

## Game state object

`state` is a complete snapshot, so a client can always redraw from the latest one:

`game_id, status (waiting|active|finished|aborted), version, time_control_seconds, increment_seconds,
players {white, black}, fen, turn, ply, moves [{ply, uci, san}], last_move, is_check, legal_moves, captured,
clocks {white_ms, black_ms, running}, draw_offered_by, result, result_reason, created_at, started_at, finished_at,
server_time`.

- `version` increases with every state change. Ignore snapshots older than the one you hold.
- `legal_moves` (UCI) lists moves for the side to move, for highlighting only. The server re-validates every move.
- `result`: `white_win`, `black_win`, `draw`, or `null`.
- `result_reason`: `checkmate`, `stalemate`, `insufficient_material`, `threefold_repetition`, `fifty_move_rule`,
  `resignation`, `timeout`, `timeout_vs_insufficient_material`, `draw_agreement`, `never_started`.

## Clocks

Clock values are the time remaining **at `server_time`**. A client may animate the running side's countdown locally,
but must resynchronise on every event. Clients never send times, and the server ignores any attempt to.

## Close codes

Before closing a socket the server sends `closing` with the code it is about to use. **Act on that message** and close
your side: on the hosted deployment the close frame itself did not arrive, and the browser saw only a reasonless
`1006` about 20 seconds later. The same code is still sent in the close frame. (A disallowed origin is refused during
the handshake, so it gets neither.)

| code | meaning | client should |
| --- | --- | --- |
| 1009 | message over 4 KB | fix the client |
| 4400 | five invalid messages in a row | fix the client |
| 4401 | authentication failed or first message was not `auth` | sign in again |
| 4403 | not a player in this game, or disallowed origin | stop |
| 4404 | game not found | stop |
| 4408 | no `auth` within 10 s | reconnect |
| 4409 | replaced by a newer connection for the same player | do **not** auto-reconnect |
| 4410 | nothing received for 60 s | reconnect (send `ping` every 20–25 s) |
| 4429 | more than 20 messages in a second, or too many sockets (100) waiting to sign in | back off |

## Disconnection policy

- The clock keeps running while a player is away. There is no separate abandonment forfeit: flag fall handles it.
- Reconnect at any time before the game ends. `connected` carries the full state.
- One live socket per player per game: the newest connection wins.
- Flag fall is detected by a server task from database state, so it happens even if nobody is connected or the server
  has restarted. A game that expired during server downtime is flagged when the server returns.

## Scaling note

Connection rooms are held in process memory, so run **one** API instance. Multiple instances would need a pub/sub layer
(for example Redis or PostgreSQL `LISTEN/NOTIFY`). Game state and matchmaking already live in PostgreSQL.
