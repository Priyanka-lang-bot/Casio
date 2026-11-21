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
| 1 | PDF / CSV / SMS ingestion | ✅ `app/importers/`, Import Statements page | 2 |
| 2 | Automatic categorisation | ✅ keyword rules + optional AI (`app/ai.py`), confidence and reason on every row | 2 |
| 3 | Learning correction loop | ✅ `app/learning.py`, Learned Rules page, "Remember this?" dialog | 3 |
| 4 | Recurring payments & subscriptions | ✅ `app/recurring.py`, Subscriptions page, alerts on Overview | 3 |
| 5 | Persistent financial profile | ✅ Financial Profile (Phase 1); grows into Money Model with snapshots | 1 → 4 |
| 6 | Goals + what-if simulator | goals, goal_contributions, scenarios; deterministic simulator in `finance.py` | 4 |
| 7 | Proactive nudges | nudges table + checks after each import/transaction | 5 |
| 8 | Monthly review reports | monthly_reports table, Reports page | 5 |
| 9 | Responsible AI guardrails | coach system rules + output check blocking securities advice | 5 |

## 5. Tables still to add (created in the phase that uses them)

Creating tables only when their feature is built keeps each migration small
and avoids guessing at columns.

- Phase 4: `budgets`, `financial_goals`, `goal_contributions`, `financial_snapshots`, `forecasts`, `financial_scenarios`
- Phase 5: `financial_nudges`, `monthly_reports`, `ai_conversations`, `ai_insights`

## 6. Phase 2 status: Smart Import (done and tested)

How it works is in `backend/app/importers/README.md`.

| Item | Status |
|---|---|
| CSV: preamble lines, `,` `;` tab `|`, many column names, Debit/Credit or Amount (+Dr/Cr), day-first dates | ✅ |
| PDF: ruled tables, or text lines with Debit/Credit columns or running balance; password and damaged files explained | ✅ |
| Scanned PDFs detected and explained (OCR is a later add-on) | ✅ |
| SMS: paste or .txt upload, OTPs/offers skipped, balance never mistaken for the amount | ✅ |
| Review before save: edit date, description, amount, in/out, category; untick rows; filters | ✅ |
| Duplicates: exact matches with saved transactions unticked; same date+amount flagged; re-uploaded file warned | ✅ |
| Categorisation with confidence, reason and "Please check" below 60% | ✅ |
| "Change similar rows too?" within one import (cross-import learning is Phase 3) | ✅ |
| Provenance: source, import batch, original text, balance, dedupe fingerprint on every saved transaction | ✅ |
| Undo a whole import | ✅ |
| Optional AI (Claude) for uncertain rows, privacy-scrubbed, with rule fallback | ✅ (needs `ANTHROPIC_API_KEY`) |
| Tests | 65 backend tests (38 new) + 19-check browser test |

Not yet: OCR for scanned PDFs, Excel files (save as CSV), choosing which bank
account an import belongs to.

## 7. Known gaps and notes

- No real email sending yet (console mode). To go live, add an email
  provider in `app/email.py`.
- Data export and account deletion (Settings) are planned for Phase 6.
- The login attempt limiter is in memory, which is fine for one server.
- shadcn/ui components were added by hand (`src/components/ui/`) because the
  shadcn download site was blocked from the build machine; they are the
  standard shadcn source and work with `npx shadcn add` later.

## 8. Phase 3 status: Learned Rules and Subscriptions (done and tested)

### Adaptive learning (`backend/app/learning.py`)

| Item | Status |
|---|---|
| Every category change saved as a correction (`category_corrections`), with no rule made automatically | ✅ |
| "Remember this for next time?" after a change, on Transactions and on the import review screen | ✅ |
| Preview before saving: how many earlier transactions would change (with examples), rows in this import, conflicts | ✅ |
| Recommendation from history: "you've made this change 2 times" → suggests a rule; mixed history → suggests one-off | ✅ |
| Shop-name rules and "description contains" rules; generic words like "UPI" refused | ✅ |
| Priority (high / normal / low), then the more specific rule wins; overlapping rules shown on the Rules page | ✅ |
| Same match with a new category replaces the old rule (warned first) | ✅ |
| Confidence ("% reliable") drops when the user keeps changing what a rule picked; weak rules flagged | ✅ |
| Rules run before keyword rules and AI, on imports and new transactions; marked "Your rule" with the reason | ✅ |
| Undo / remove / pause: transactions go back exactly to their earlier category (`rule_applications`) | ✅ |
| Categories the user picked by hand are never changed by a rule | ✅ |

### Recurring payments (`backend/app/recurring.py`)

| Item | Status |
|---|---|
| Weekly, fortnightly, monthly, quarterly, yearly, from gaps between payments to the same shop | ✅ |
| Steady amounts required, except bills (electricity etc.); random spending (food orders) ignored | ✅ |
| Shops that mix a subscription with one-off buys are checked by amount | ✅ |
| Next payment (labelled Forecast), yearly cost, price history, "why CASIO thinks this repeats" | ✅ |
| Alerts: new, price up/down, unusual bill, missed payment, charged after you cancelled, "do you still use it?" | ✅ |
| Usage is asked, never assumed; "You could save" only counts services the user said they don't use | ✅ |
| Mark as cancelled / not a regular payment (remembered), rename | ✅ |
| Judged against the latest imported transaction, so an old statement doesn't look "missed" | ✅ |
| Tests | 86 backend tests (21 new) + 25-check browser test |

Demo data: `docs/samples/sample-6-months.csv` (June to November 2026).
