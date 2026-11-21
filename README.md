# CASIO

Adaptive AI personal finance coach. *Don't just track money. Understand it.*

This is the real application (no landing page). Phase 1 is done: accounts,
login, the app shell with all 12 sections, the financial profile, manual
transactions and a basic dashboard. See [docs/ROADMAP.md](docs/ROADMAP.md)
for what's built, what's next and how it maps to the competition requirements.

## What's inside

| Part | Tech | Folder |
|---|---|---|
| Web app | Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui, Recharts | `frontend/` |
| API | Python 3.12+, FastAPI, SQLAlchemy 2, Alembic migrations | `backend/` |
| Database | PostgreSQL 16 | — |

The browser only talks to the Next.js app. Anything under `/api/*` is
forwarded to FastAPI, so the login cookie stays on one website.

## Run it on your computer

You need: **Node.js 20+**, **Python 3.12+** and **PostgreSQL 16** installed.

### 1. Create the database (once)

```bash
psql -U postgres -c "CREATE USER casio WITH PASSWORD 'casio_dev_password' CREATEDB;"
psql -U postgres -c "CREATE DATABASE casio OWNER casio;"
psql -U postgres -c "CREATE DATABASE casio_test OWNER casio;"   # used by the tests
```

### 2. Start the backend (terminal 1)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then edit values if needed
alembic upgrade head               # creates/updates tables; never deletes data
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 3. Start the web app (terminal 2)

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000 and create an account.

**Forgot password:** no email service is set up yet, so the reset email is
printed in the backend terminal (terminal 1). Copy the link from there.

## Run the tests

```bash
cd backend && source .venv/bin/activate && pytest     # 27 tests
cd frontend && npx tsc --noEmit && npm run lint && npm run build
```

## Rules this codebase follows

- Money is stored as exact decimals (`NUMERIC(14,2)`) and sent to the browser
  as strings like `"1500.25"`, never as floating point numbers.
- All calculations happen in `backend/app/finance.py`. The AI coach (later)
  will call these functions; it never does maths itself.
- Every number on screen is labelled **Actual** (from transactions) or
  **Your estimate** (from the profile). Forecasts will be labelled **Forecast**.
- Every query is filtered by the signed-in user. Other users' data returns 404.
- Secrets live in `.env` files, which are never committed.
