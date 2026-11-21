# Deploying CASIO

CASIO runs on Vercel as two projects built from this one repository, plus a Neon Postgres database.

| Part | Vercel project | Root directory | Production URL |
|---|---|---|---|
| Web app (Next.js) | `casio` | `frontend` | https://casio-three.vercel.app |
| API (FastAPI) | `casio-api` | `backend` | https://casio-api.vercel.app |
| Database | Neon (Vercel Marketplace, Free plan, region iad1) | | connected to `casio-api` |

The browser only talks to the web app. Next.js forwards every `/api/*` request to the API (`frontend/next.config.ts`), so the login cookie stays on one site and no CORS setup is needed.

## Automatic deploys

Both projects are linked to `Priyanka-lang-bot/Casio` on GitHub.

- A push or merge to `main` deploys both projects to production.
- A pull request gets preview deployments. Previews have no environment variables, so they can't sign in. Test on production, or add the variables to the Preview environment if you need working previews.

## Environment variables

Set these in each project under **Settings → Environment Variables**. Never commit real values to git.

### `casio-api`

| Name | Value | Notes |
|---|---|---|
| `DATABASE_URL` | added by the Neon integration | pooled connection, used by the app |
| `DATABASE_URL_UNPOOLED` | added by the Neon integration | direct connection, used for migrations |
| `MIGRATE_ON_STARTUP` | `true` | runs `alembic upgrade head` when a function starts, under a Postgres advisory lock |
| `COOKIE_SECURE` | `true` | session cookie is HTTPS-only |
| `EMAIL_MODE` | `console` | password-reset emails go to the function logs (no email provider yet) |
| `FRONTEND_URL` | `https://casio-three.vercel.app` | used to build password-reset links |
| `ANTHROPIC_API_KEY` | your key, as a **Secret** | optional: turns on the AI coach, AI what-if parsing, AI categorisation and report summaries. Without it, built-in rules are used |

### `casio`

| Name | Value |
|---|---|
| `BACKEND_URL` | `https://casio-api.vercel.app` |

After changing a variable, redeploy: **Deployments → ⋯ → Redeploy**.

## Health check

`GET https://casio-api.vercel.app/api/health` (also reachable at `https://casio-three.vercel.app/api/health`):

```json
{"status":"ok","database":"ok","schema":"<alembic revision>","ai":"configured|not_configured"}
```

It returns HTTP 503 with `"database":"unreachable"` when the database can't be reached.

## Database migrations

Migrations live in `backend/alembic/versions`. With `MIGRATE_ON_STARTUP=true`, the newest migration is applied automatically on the first request after a deploy. To run them by hand from a machine that can reach Neon:

```bash
cd backend
DATABASE_URL="<DATABASE_URL_UNPOOLED value>" python -m app.migrate
```

The local development database (`docker compose`, `localhost:5432`) is separate and is never used in production.

## Testing the live site

The browser tests accept a base URL:

```bash
BASE_URL=https://casio-three.vercel.app node docs/e2e-planning-test.js
```

Note that this test creates an account and then deletes it at the end.
