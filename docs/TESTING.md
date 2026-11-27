# Testing

## Layers

| Suite | Command | What is real | Covers |
| --- | --- | --- | --- |
| Backend unit and integration | `cd backend && pytest` | PostgreSQL; the app in-process | rules, clock, services, locking, REST, WebSocket protocol, schema and migrations, hardening |
| Live matches | `cd backend && pytest tests_live` | a separate API process, HTTP, WebSockets, PostgreSQL, real time | whole games between two clients |
| Frontend | `cd frontend && npm test` | React in jsdom; the API and socket are fakes | screens, board input, socket and reducer behaviour |
| Browser | `cd frontend && npm run test:e2e` | Google Chrome, one isolated session per player, the real stack | the user's path through the app |

The two backend suites erase the `_test` database they use and must not run at the same time.

## Live match suite

Each match is two clients, each with its own account and socket, matched through the real queue. A separate
`python-chess` board follows along and checks the position, move number and check status that **both** players
receive after every move. The API's log must contain no errors at the end of the run.

The suite writes `match-report.json` from the games that actually ran. Run on 26 November 2026 (71 tests passed in
9 min 6 s):

| Measure | Count |
| --- | --- |
| Match sessions (games created) | **82** |
| Moves accepted by the server | 6,344 |
| Distinct test scenarios that played a match | 36 (64 counting each parameter variant) |
| Games played to a final state | 51 |
| Games deliberately left unfinished once the behaviour under test had been checked | 31 |

Final states of those 51 games: resignation 18, insufficient material 8, checkmate 6, fifty-move rule 6, draw
agreement 3, never started (aborted) 3, timeout 3, stalemate 2, threefold repetition 1, timeout against insufficient
material 1. Sixteen of the games are complete random legal games, whose endings come from the rules rather than from a
script chosen to reach them.

### Scenarios

| Area | Checked |
| --- | --- |
| Endings | checkmate by each side, stalemate, threefold repetition, insufficient material, fifty-move rule |
| Special moves | castling (both sides, both wings), refused through check and after the king moved; en passant by each side and after it expires; promotion to each piece, refused with no piece chosen |
| Illegal input | impossible moves, bad squares, ignoring check, moving a pinned piece, out of turn, opponent's piece, after the game ended |
| Draws and resignation | resign by each side over the socket and over REST; agreed, declined, crossing and invalid draw offers |
| Races | both players resigning at once, a move racing a resignation, the same move sent five times; one result and one statistics update each |
| Connections | each player disconnecting and returning, moves made while away, clocks running with nobody connected, a newer connection replacing the old one |
| Persistence | a game continuing after the API process is restarted; history, paging and statistics over several games |
| Matchmaking | 20 players joining at once form exactly 10 games; cancel, double join, join while playing, time controls kept apart; abandoned games aborted without statistics |
| Real clocks | white and black flag falls on 3-minute games (within 178–183 s), a flag while both are away, and a draw when the opponent cannot mate |
| Security | bad tokens, outsiders (REST and socket), foreign origin, oversized and flooding messages, forged results and clocks, CORS, duplicate accounts, errors not repeating passwords |

The unstarted-game timeout is shortened to 8 s for this suite. The sign-in rate limit is raised, and is tested
separately in `tests/test_hardening.py`.

## Browser tests

Six scenarios: two sessions playing to checkmate through a refresh, a disconnect and a second tab; a tampered
client's illegal move being rejected; drag and drop, captures, promotion and an agreed draw; cancelling and resuming
a search; and layout at 320, 375, 768 and 1366 px.

On 26 November 2026 all 6 passed against the **Docker production build**, so the Content-Security-Policy was in
force. The two-player scenarios that check for it reported no console errors.

## Docker checks (run once by hand, 26 November 2026)

- `docker compose up` brought all three containers to healthy; migrations ran on start; the API runs as a non-root user.
- After `docker compose down` and `up`, the database held the same 84 users, 41 finished games and 2,181 moves.
- The API log showed no errors.

## Continuous integration

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on every push to `main` and every pull request:
backend lint, strict type check, tests and dependency audit; the live match suite; frontend lint, type check, tests,
build and audit; and the browser tests against the Docker stack.

[Run 45894022549](https://github.com/Divine-K/multiplayer-chess-platform/actions/runs/45894022549), for commit
`9fcf998`, passed all four jobs. Its own match report matched the local one: 71 live tests, 82 match sessions and
6,344 moves. The 6 browser tests passed, and `pip-audit` and `npm audit` reported no known vulnerabilities.

The local live run above was made before a late change to the sweeper's clock-update timing (below). The CI run
includes that change.

## Move latency (one local measurement)

Time from one client sending a move until **both** had received the new position, on the Docker stack on a
development Mac, with no network between client and server. Each game played 60 moves with a 150 ms pause between
them.

| Games at once | Moves measured | Median | 95th percentile | Slowest |
| --- | --- | --- | --- | --- |
| 1 | 60 | 21 ms | 30 ms | 98 ms |
| 10 | 600 | 11 ms | 24 ms | 99 ms |
| 25 | 1,500 | 10 ms | 52 ms | 264 ms |

This is not a load test and says nothing about a small hosted instance.

## Defects found while testing

- **Passwords in error responses.** Validation errors (HTTP 422) repeated the rejected input, so a registration or
  sign-in request that failed validation sent the password back, or the whole request body when a field was missing.
  Errors now contain only the type, location and message, with regression tests in both backend suites.
- **Intermittent test failure, introduced and fixed on the same day, before pushing.** The new idle sweeper sent its
  first clock update as soon as it woke, which occasionally arrived between two moves. It failed one early run, and
  again on the 21st run of a repeat loop. The 5 s delay was restored and given a test; 40 consecutive runs then
  passed.

Two other failures in the first live runs were mistakes in the tests themselves: a wrong expected error code, and
four pairings started at once that matched each other's players.

## Hosted deployment

Checked on 26 November 2026 against the live site.

**Automated checks, using no accounts:** health and database readiness in production mode; `http` redirects to
`https`; security headers on the API and web app; page addresses load directly; a protected route returns 401; the API
approves the web app's origin and not a foreign one; a foreign origin is refused at the WebSocket handshake.

**Two defects appeared only on the hosted service.** Local, CI and Docker tests had all passed.

| Defect | Cause and fix | Retest on the live site |
| --- | --- | --- |
| The sign-in limit never triggered | Identifying visitors by counting `X-Forwarded-For` entries failed with 1 and 2. The API now reads `CF-Connecting-IP` | 20 attempts allowed, then 429. Invented `X-Forwarded-For`, `True-Client-IP` and `X-Real-IP` values stayed blocked; supplying `CF-Connecting-IP` got 403 |
| Close codes were lost: the browser got 1006 after 20–30 s | The close frame did not arrive; which part of the hosted path loses it is unknown. The server now sends a `closing` message first and the client acts on it | In a browser: 4401 and 1009 announced in under 1 s, 4408 at 10.6 s |

After the fixes: 205 backend and 117 frontend tests, 71 live match tests (82 match sessions) and 6 browser tests on
Docker passed locally, and all GitHub jobs passed for commit `7e486d5`.

**Manual two-player test:** the project owner then ran a checklist on the live site and reported that all of it
passed: matching, moves and clocks in both sessions, refresh during a game, a second tab taking over without the tabs
looping, disconnect and resume, finishing a game, and saved results and history. This was not automated, and the
browser and timings were not recorded. The optional phone game was not separately reported.

## Not tested

- Firefox, Safari, and physical phones or tablets, specifically.
- On the hosted site: a measured cold start or latency, and whether blocking one visitor leaves a visitor on a second
  network unaffected (a unit test covers this with simulated headers).
- Load beyond 25 simultaneous games, long-running soak tests, or database failover.
- Screen readers (keyboard play is tested).
