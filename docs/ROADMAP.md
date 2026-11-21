# CASIO architecture and roadmap

## 1. What was in the repository

The GitHub repository `Priyanka-lang-bot/Casio` was empty (no commits), so
there was no existing code to preserve. Phase 1 sets up the foundation using
the stack from the brief.

## 2. How it fits together

```
Browser ──► Next.js (frontend/, port 3000)
              │  pages, forms, charts
              │  /api/*  is forwarded ──►  FastAPI (backend/, port 8000)
              │                              │  auth, validation, all money maths
              │                              ▼
              │                           PostgreSQL (Alembic migrations)
```

- **Login sessions.** On login the backend creates a random token, stores
  only its SHA-256 hash in `user_sessions`, and sets it as an `httpOnly`,
  `SameSite=Lax` cookie. Logout deletes the row, so a copied cookie stops
  working at once. "Remember me" makes it last 30 days; otherwise 12 hours
  and it ends when the browser closes.
- **Passwords** are hashed with Argon2id. 5 wrong attempts for an email lock
  it for 15 minutes. Error messages never reveal whether an email has an account.
- **Protected pages.** `src/proxy.ts` sends visitors with no cookie to
  `/login`; the `(app)` layout then asks the backend who's signed in on every
  page load; and every API endpoint checks again. The backend check is the
  one that matters.
- **Data isolation.** Every table with personal data has `user_id` with a
  foreign key, and every query filters on it.
- **Audit log** (`audit_logs`) records sign-ins, sign-outs, password resets and
  every create/update/delete by id only (no amounts, descriptions or passwords).

### Key backend files

| File | Purpose |
|---|---|
| `app/models.py` | All database tables |
| `app/finance.py` | All calculations (Decimal only) |
| `app/routers/auth.py` | Register, login, logout, forgot/reset password |
| `app/routers/profile.py` | Financial profile CRUD + monthly summary |
| `app/routers/transactions.py` | Categories, transactions CRUD + filters |
| `app/routers/overview.py` | Dashboard numbers |
| `app/importers/` | Smart import base types + Phase 2 plan |
| `alembic/versions/` | Database migrations |

## 3. Phase 1 status (done and tested)

| Item | Status |
|---|---|
| Register / login / logout / remember me / show-hide password | ✅ |
| Forgot password (email printed to backend console until an email service is added) | ✅ |
| 12-section app shell, responsive with a phone menu | ✅ all pages exist; 8 are honest "not built yet" pages |
| Financial profile: income, regular costs (fixed/variable), assets incl. emergency fund, debts | ✅ add / edit / delete |
| Monthly plan: income, spending, left over, net worth, emergency-fund months | ✅ calculated in backend |
| Transactions: add, edit, delete with confirmation, categories, filters, search | ✅ double-click safe |
| Overview: month income/expenses/left over, savings rate, 6-month chart, category breakdown, recent transactions, plan | ✅ |
| Settings: account info, currency (locked once transactions exist) | ✅ |
| Database: users, sessions, profiles, accounts, categories (15 built-in), transactions with provenance, import batches, import errors, income sources, expense items, assets, liabilities, audit log | ✅ |
| Tests | 27 backend tests + a 40-check browser test |

## 4. Competition requirements map

| # | Requirement | Where it will live | Phase |
|---|---|---|---|
| 1 | PDF / CSV / SMS ingestion | `app/importers/`, Import Statements page | 2 (tables ready) |
| 2 | Automatic categorisation | importer pipeline: rules → keywords → AI; `category_source/confidence/reason` columns exist | 2 |
| 3 | Learning correction loop | `categorization_rules` table, "apply to similar?" prompt, undo | 3 |
| 4 | Recurring payments & subscriptions | detection job over transactions, Subscriptions page | 3 |
| 5 | Persistent financial profile | ✅ Financial Profile (Phase 1); grows into Money Model with snapshots | 1 → 4 |
| 6 | Goals + what-if simulator | goals, goal_contributions, scenarios; deterministic simulator in `finance.py` | 4 |
| 7 | Proactive nudges | nudges table + checks after each import/transaction | 5 |
| 8 | Monthly review reports | monthly_reports table, Reports page | 5 |
| 9 | Responsible AI guardrails | coach system rules + output check blocking securities advice | 5 |

## 5. Tables still to add (created in the phase that uses them)

Creating tables only when their feature is built keeps each migration small
and avoids guessing at columns.

- Phase 3: `categorization_rules`, `recurring_payments`, `subscriptions`
- Phase 4: `budgets`, `financial_goals`, `goal_contributions`, `financial_snapshots`, `forecasts`, `financial_scenarios`
- Phase 5: `financial_nudges`, `monthly_reports`, `ai_conversations`, `ai_insights`

## 6. Next: Phase 2, Smart Import

The detailed plan is in `backend/app/importers/README.md`. In short: upload →
safety checks → parse (CSV column mapping, PDF text/tables, SMS templates) →
categorise → **review screen** where the user fixes anything and un-ticks
duplicates → confirm. AI never invents a missing date or amount.

Needs: `pandas`, `pdfplumber`, and (for the AI step) an LLM API key in
`backend/.env`. Without a key, categorisation falls back to keyword rules.

## 7. Known gaps and notes

- No real email sending yet (console mode). To go live, add an email
  provider in `app/email.py`.
- Data export and account deletion (Settings) are planned for Phase 6.
- The login attempt limiter is in memory, which is fine for one server.
- shadcn/ui components were added by hand (`src/components/ui/`) because the
  shadcn download site was blocked from the build machine; they are the
  standard shadcn source and work with `npx shadcn add` later.
