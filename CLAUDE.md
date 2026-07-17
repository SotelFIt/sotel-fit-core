# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Sotel Fit Core is a Portuguese-language SaaS platform for AI-assisted personal training. Clients arrive via WhatsApp (Twilio) or a Landbot chatbot, go through onboarding, pay via Stripe, and receive AI-generated (Anthropic) workout and diet plans that the admin reviews and publishes. The product roadmap lives in `Fases de evolução do projeto Sotel Fit Core.txt` — the project is currently in the early phases (make it work operationally; no advanced automation yet).

## Repository layout — read this first

The README describes a target monorepo (`apps/web` Next.js, `apps/api`) that is **empty scaffolding** (`.gitkeep` placeholders only), part of a planned migration that hasn't happened. The real, deployed code is:

- **`app/`** — the FastAPI backend (Python 3.11). Deployed via the root `Procfile` (`cd app && uvicorn main:app`). Entry point: `app/main.py`.
- **`frontend/`** — Vite + React 19 + TypeScript dashboard (not Next.js, despite the README). Deployed to Vercel via root `vercel.json`. State: zustand (`src/store/authStore.ts`); HTTP: axios (`src/services/api.ts`).
- **`tests/`** — dependency-free unit tests (stdlib `unittest` only).
- `apps/`, `packages/`, `infrastructure/`, `docs/`, `sotel-client/` — empty placeholders. Root `config.py`, `database.py`, `security.py` are empty files.

### Historical cruft — do not treat as canonical

The tree contains many leftovers: `fix_*.py` routers/services (`fix_evolution2.py`, `fix_cut3.py`, …), `*.bak` / `*.backup` / `*.txt` copies of modules, a nested `app/app/` duplicate, and one-off scripts (`add_column.py`, `check_tables.py`, `reset_lead.py`). **The source of truth is whatever `app/main.py` actually imports and includes.** Don't extend or "fix" the orphaned copies; when editing, confirm you're in the file that's actually wired up.

## Commands

### Backend (run from `app/`)

```bash
cd app
pip install -r requirements.txt   # app/requirements.txt is the full list; the root one is a subset
uvicorn main:app --reload
```

`core/security.py` raises at import unless `JWT_SECRET_KEY` and `LANDBOT_SECRET_TOKEN` are set (a root `.env` is loaded via python-dotenv). `DATABASE_URL` defaults to `sqlite:///./test.db`; production is PostgreSQL on Railway.

### Tests

Two independent suites:

```bash
# 1. Pure env-resolver tests (no dependencies, no network/DB) — run from repo root:
python -m unittest discover -s tests -p "test_*.py"

# 2. API integration tests (pytest + in-memory SQLite) — run from repo root:
pytest app/tests/
```

`app/tests/conftest.py` injects the required env vars; `test_full_flow.py` does `sys.path.insert(0, 'app')`, so the pytest suite must be run from the repo root. Run a single test with `pytest app/tests/test_full_flow.py::test_jwt_invalido`.

### Frontend

```bash
cd frontend
npm install
npm run dev      # Vite dev server
npm run build    # tsc -b && vite build
npm run lint     # eslint .
```

## Backend architecture

Flat layered structure under `app/` (imports are top-level, e.g. `from core.database import ...` — the working directory must be `app/`):

- **`routers/`** — FastAPI routers, registered explicitly in `main.py` (some inside try/except so a broken router degrades instead of crashing startup). Key ones: `landbot.py` (chatbot webhook), `twilio_webhook.py` / `twilio_status.py` (WhatsApp), `stripe_webhook.py` / `stripe_checkout.py`, `clients.py`, `auth.py`, `admin.py`, `ai_admin.py`, `lead_onboarding.py`, `timeline.py`, `photos.py`, `checkin.py`, `cron.py`.
- **`services/`** — business logic: AI plan/diet generation (`ai_*.py`, `diet_ai.py`, `workout_ai.py`, `metodo_sotel.py`), Twilio conversation flow (`twilio_flow_service.py` + `models/conversation_state.py`), reminders (`workout_reminder.py`, `checkin_reminder.py`).
- **`models/`** — SQLAlchemy models on the shared `Base` from `core/database.py`. `main.py` does `from models import *` so every model registers before `create_all`.
- **`schemas/`** — Pydantic request/response models.
- **`core/`** — `database.py` (engine/session, SQLite-vs-Postgres pool config), `security.py` (JWT), `twilio_env.py`, `phone.py`, middleware/observability.

### Database migrations

There is **no Alembic in practice** (the `alembic/` dir is vestigial). Schema changes go in `app/migrate.py`: idempotent raw-SQL statements (`ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`) executed at startup, each wrapped so a failure rolls back and continues. Add new schema changes there, plus the SQLAlchemy model change. `Base.metadata.create_all` also runs at startup for new tables.

### Background jobs

APScheduler cron jobs are registered in `main.py`'s startup event (check-in reminders weekdays 08:00, workout reminders daily 07:00). There is also a `routers/cron.py` for externally-triggered jobs.

### Auth and security conventions

- JWT via PyJWT in `core/security.py`. Token payloads carry a `type` claim (`access`, `refresh`, `magic`) and `verify_token` enforces it — a magic-link token can never be used as a Bearer access token.
- Magic-link flow: signed token → `/auth/magic-link/{id}` and `/auth/magic-link/exchange`. **Route order matters**: literal routes like `/exchange` must be declared before parameterized `/{client_id}` routes or FastAPI shadows them (this was a real production bug, see commit 421d9c6).
- **IDOR protection is a hard convention**: client-facing endpoints must scope every query by the authenticated `client_id` from the token, never trust a client ID from the path/body alone (see commit f651b43).
- Webhooks authenticate via shared secrets (`LANDBOT_SECRET_TOKEN`, Twilio/Stripe signature validation in `core/security_webhook.py`).
- CORS is an explicit allowlist in `main.py` (Vercel domains); add new frontend origins there.

### Twilio env-var pattern

Template SIDs are resolved through pure functions in `core/twilio_env.py` (stdlib-only, no SDK imports) so they can be unit-tested without the app's heavy dependencies. During naming transitions, resolvers accept the official English name with the legacy Portuguese name as fallback (e.g. `TWILIO_TEMPLATE_RETENTION` → `TWILIO_TEMPLATE_RETENCAO`). A `None` result means the caller must skip the Twilio call, not error. Follow this pattern for new template variables.

### AI content publishing

AI-generated plans/diets are drafts for admin review. `services/client_safe.py` (`make_client_safe`) strips administrative blocks, draft markers, and internal-method notes before content reaches a client. Anything shown to clients from AI output must pass through it.

## Conventions

- Code comments, log messages, docstrings, and commit messages are in **Portuguese** (pt-BR).
- Commits follow conventional-commit style with pt-BR descriptions: `fix(retention): aceitar TWILIO_TEMPLATE_RETENTION com fallback RETENCAO`.
- `main` is production; work happens on `feature/*` / `fix/*` branches merged via PR.
- Deployment configs: root `Procfile` (Railway, active), `app/render.yaml` (Render, legacy), root `vercel.json` (frontend). Runtime pinned to Python 3.11.8 in `app/runtime.txt`.
