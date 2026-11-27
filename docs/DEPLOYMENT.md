# Deployment

**Status: live since 26 November 2026.**

- Web app: https://multiplayer-chess-2n5.pages.dev
- API: https://multiplayer-chess-api-2uro.onrender.com

The results of the checks are in [TESTING.md](TESTING.md#hosted-deployment). The steps below reproduce the setup.

| Part | Host | Why |
| --- | --- | --- |
| Web app (static files) | Cloudflare Pages | free static hosting with HTTPS |
| API and WebSockets | Render, free web service | builds the Dockerfile; supports WebSockets |
| PostgreSQL | Neon, free plan | does not expire, unlike Render's free database |

## Free plan limits (checked November 2026; confirm before relying on them)

- **Render:** a free web service stops after 15 minutes without inbound traffic and takes about a minute to start
  again. Incoming WebSocket messages count as traffic, and the app pings every 20 s during a game. A workspace gets
  750 free instance hours a month. Render may restart a free service at any time.
  ([Render: free instances](https://render.com/docs/free))
- **Neon:** 100 compute hours a month and 1 GB of storage per project; compute suspends after 5 minutes of
  inactivity. ([Neon: free plan](https://neon.com/faqs/free-plan-limits-and-quotas))
- **Cloudflare Pages:** static requests are free; the plan limits builds per month.
  ([Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/))

What this means for the app: after a quiet spell the first visitor waits about a minute. While no game is
unfinished, the timeout sweeper does not query the database, so Neon can suspend. If the API is stopped while a
game is running, the clocks are still correct: the game is flagged when the API returns.

## 1. Database (Neon)

1. Create a project with PostgreSQL 16, in a region near the API.
2. Copy the connection string (`postgresql://…?sslmode=require`). Use the **direct** connection, not the pooled one,
   for this single long-running process. The API selects the correct driver itself.

## 2. API (Render)

1. New → Blueprint, and choose this repository. Render reads [`render.yaml`](../render.yaml).
2. When asked, set `DATABASE_URL` to the Neon string. For `CORS_ORIGINS` enter a placeholder such as
   `["https://example.invalid"]`; you will correct it after step 3.
3. Deploy. The container runs `alembic upgrade head` before starting, so the schema is created automatically.
4. Check `https://<service>.onrender.com/health/ready` returns `{"status":"ready","database":"ok"}`.

## 3. Web app (Cloudflare Pages)

Create a Pages project connected to the repository:

| Setting | Value |
| --- | --- |
| Root directory | `frontend` |
| Build command | `npm run build` |
| Output directory | `dist` |
| Variable `VITE_API_BASE_URL` | `https://<service>.onrender.com` |
| Variable `NODE_VERSION` | `24` |

The build writes a `_headers` file with the security policy for exactly that API address. Pages serves
`index.html` for unknown paths when there is no `404.html`, which client-side routes need.

Then set `CORS_ORIGINS` in Render to `["https://<project>.pages.dev"]` (exact origin, no trailing slash) and
redeploy the API.

## 4. Verify

- [ ] `/health/ready` is 200, and the site loads over HTTPS with no console errors.
- [ ] Register two accounts in two separate browser sessions; they are matched.
- [ ] The socket connects over `wss://`; moves appear on both screens.
- [ ] Refresh mid-game restores the position. Finish a game; history and statistics update.
- [ ] A wrong origin is refused by the API.
- [ ] **Rate limit behind the proxy.** Send more than 20 requests with the body `{}` to `/api/v1/auth/login` within a
      minute. They need no password and create nothing; the later ones must return 429. While blocked, repeat with
      an invented `X-Forwarded-For` header: still 429.
- [ ] **Socket close reasons.** A socket that sends a bad token receives `closing` with code 4401 at once.

### Identifying clients behind Render

The rate limit needs the visitor's real address. `render.yaml` sets `CLIENT_IP_HEADER=cf-connecting-ip`, a header
that Cloudflare, in front of Render, sets itself; a request that tried to supply it was refused with 403.

Counting `X-Forwarded-For` entries (`TRUSTED_PROXY_HOPS`) did not work here: with 1 and with 2, the limit never
triggered. With 1, a local test showed that a last entry which changes per request has exactly that effect. Check the
limit on the real host after any change: a wrong setting can silently switch it off. On another host, only set
`CLIENT_IP_HEADER` to a header that the host overwrites on every request.

## Running the whole stack with Docker

```bash
cp .env.example .env      # set POSTGRES_PASSWORD (letters and digits) and JWT_SECRET_KEY
docker compose up --build
```

The web app is at `http://localhost:8080` and the API at `http://localhost:8000`. Change `FRONTEND_PORT` and
`BACKEND_PORT` if those are taken. PostgreSQL is not published to the host, and its data is kept in a volume
(`docker compose down -v` deletes it). The ports listen on this machine only, and this setup has no TLS; it is for
local use.

## Operating notes

- Run **one** API instance: live connections are held in memory.
- Changing `JWT_SECRET_KEY` signs everyone out.
- Rate-limit counts are in memory and reset on restart.
