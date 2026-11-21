# CASIO

Adaptive AI personal finance coach. *Don't just track money. Understand it.*

**Live:** https://casio-three.vercel.app (API: https://casio-api.vercel.app/api/health)

The home page is an editorial landing page with a live preview of the
wallet. Signed in, every feature is a numbered card in a leather wallet
(`/wallet`): the left holder "Everyday Money" holds cards 1 to 7, the right
holder "Plan & Grow" holds cards 8 to 14. Light (ivory) and dark (charcoal)
themes switch from the top bar and are remembered in the browser.

**Try CASIO Demo** opens a private sandbox with six months of fictional INR
data (salary, rent, UPI merchants, subscriptions with a price rise, budgets,
goals, rules). Each visitor gets their own copy, it can be reset from the
banner or Settings, and it is deleted after 24 hours.

Every section works:

| Section | What it does |
|---|---|
| Overview | This month's money in/out, 6-month chart, categories, proactive nudges, "Try with sample data" |
| Transactions | Add, edit, delete, search, filter; shows how each category was chosen |
| Import Statements | CSV, PDF and bank SMS; review and fix before saving; duplicates flagged; undo an import; sample files in the demo |
| Learned Rules | Fix a category once, CASIO asks whether to remember it; edit, pause, undo rules |
| Budgets | Monthly limits per category, spent/left, month-end forecast, suggested amounts |
| Subscriptions | Regular payments found automatically, price rises, missed payments, "do you still use it?", add/edit/delete your own, next-30-days list |
| Financial Profile | Income, regular costs, assets, debts (your estimates) |
| Money Model | One picture combining actuals, estimates, plans and forecasts, with monthly snapshots |
| Goals | Targets, contributions, progress, "on track / behind" with the amount needed |
| What-If Simulator | Live sliders (income, all spending, extra saving, one-off purchase) that recalculate as you drag; ask in plain words or build a scenario; effect on savings and goals |
| Spending Insights | Category changes vs last month, usual month by category, unusual one-off payments with the rule used |
| Monthly Reports | Review of any month with highlights and suggestions; download as CSV or print to PDF; AI-written summary when AI is on |
| AI Finance Coach | Answers from your real data via tools; refuses specific investment picks |
| Settings | Theme, reduce motion, hide amounts, in-app reminders (saved on the device), name, password, currency, reset demo, download all data, delete account |

All money maths happens in deterministic backend code (`backend/app/finance.py`,
`backend/app/planning.py`). The AI only reads results through tools and explains
them. Without an `ANTHROPIC_API_KEY`, CASIO still works: built-in rules
categorise transactions, parse what-if questions and answer common coach
questions, and the app says when AI is off.

See [docs/ROADMAP.md](docs/ROADMAP.md) for how it maps to the competition
requirements and [docs/DEPLOY.md](docs/DEPLOY.md) for how production is set up.

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
pip install -r requirements-dev.txt   # app + test tools
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

**Try Smart Import:** go to *Import Statements* and use the sample files
linked under the upload box (also in `docs/samples/`).

**Try learning and subscriptions:** import `sample-6-months.csv` (linked on
the Import page). While checking it, change a "Swiggy Instamart" row to
Groceries and pick "Always". Then open *Subscriptions* to see Netflix's price
rise, a missed Spotify payment and a new ChatGPT subscription, and
*Learned Rules* to edit, pause or remove the rule.

**Optional AI categorisation:** add `ANTHROPIC_API_KEY=...` to `backend/.env`
and restart the backend. Without it, CASIO uses its built-in keyword rules and
says so on the review screen. Only the description text (with numbers, UPI ids
and emails removed) is ever sent to the AI.

**Forgot password:** no email service is set up yet, so the reset email is
printed in the backend terminal (terminal 1). Copy the link from there.

## Run the tests

```bash
cd backend && source .venv/bin/activate && pytest     # 113 tests
cd frontend && npx tsc --noEmit && npm run lint && npm run build
node docs/e2e-full-qa.js                               # 45 browser checks: landing, themes, wallet, all cards, forms, mobile
node docs/e2e-import-test.js                           # browser tests (app must be running)
node docs/e2e-learning-test.js
node docs/e2e-planning-test.js                         # BASE_URL=https://... to test a live site
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
