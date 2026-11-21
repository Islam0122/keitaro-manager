# Keitaro Manager

A small web application on top of the [Keitaro](https://keitaro.io) **Admin API v1** that does two things:

1. **Campaign Creator** — takes a campaign name, a country (GEO) and a Keitaro offer, and creates a campaign with
   the right domain, group and traffic source and **two streams**: visitors from the chosen country are redirected to
   Google, everybody else goes to the offer.
2. **Campaign Editor** — adds and removes offers in an existing campaign's streams and manages the traffic split,
   keeping the shares of the active offers at exactly **100 %**.

Keitaro remains the source of truth: every number on screen is read from Keitaro. The local PostgreSQL database stores
users, the encrypted Keitaro connection, the history of created campaigns and an audit log of every write operation.

---

## Contents

1. [Features](#features)
2. [Technology stack](#technology-stack)
3. [Architecture](#architecture)
4. [Project structure](#project-structure)
5. [Prerequisites](#prerequisites)
6. [Environment variables](#environment-variables)
7. [Quick start with Docker](#quick-start-with-docker)
8. [Local development without Docker](#local-development-without-docker)
9. [Database migrations](#database-migrations)
10. [Running tests and checks](#running-tests-and-checks)
11. [API documentation](#api-documentation)
12. [Keitaro API configuration](#keitaro-api-configuration)
13. [Campaign Creator](#campaign-creator)
14. [Campaign Editor](#campaign-editor)
15. [Security considerations](#security-considerations)
16. [Known limitations](#known-limitations)

---

## Features

* **Authentication** — username/password login, JWT access tokens, brute-force lockout, every API endpoint except
  `/api/health` and `/api/auth/login` requires a token. Users are created with a CLI command or bootstrapped from env.
* **Campaign Creator** — validates the offer, domain, group and traffic source in Keitaro *before* writing anything,
  creates the campaign and both streams, verifies the result and **rolls everything back** (streams → campaign) if any
  step fails, including a failure to save the local record. The error tells exactly what was undone and what needs
  manual cleanup.
* **Campaign Editor** — list offers per stream, add (equal split or fixed share), remove (proportional rebalance),
  manual split, "split equally", "normalize to 100 %", enable/disable an offer, choose the stream, save.
  Invalid states (≠ 100 %, no active offer, duplicate or unknown offer, removing the last offer) are rejected before
  anything is sent to Keitaro. Concurrent edits are detected (HTTP 409). Multi-stream updates are compensated on
  partial failure.
* **Streams editor** — create/edit/enable/disable/delete streams with filters (GEO etc.), redirect/offers/action schemas.
* **Dashboard** — campaigns list with search and filters, resources (domains, groups, sources, offers), audit log.
* **Settings** — Keitaro URL + API key (encrypted at rest, never returned to the browser), connection test, safe URL
  for the GEO stream, password change.

## Technology stack

| Layer     | Technology |
|-----------|------------|
| Backend   | Python 3.12+ (3.13 in Docker), FastAPI, SQLAlchemy 2.0 (async), asyncpg, Alembic, Pydantic v2, HTTPX, PyJWT, cryptography |
| Frontend  | React 19, TypeScript, Vite, Tailwind CSS 4, React Router, Axios |
| Database  | PostgreSQL 16 |
| Infra     | Docker, Docker Compose, Nginx (serves the SPA and proxies `/api`) |
| Quality   | Pytest + pytest-asyncio + `httpx.MockTransport`, Ruff, ESLint, `tsc`, GitHub Actions |

## Architecture

```
Browser ──► nginx :8080 ──┬──► /           React SPA (static files)
                          └──► /api/*      FastAPI backend :8000 ──► Keitaro Admin API (HTTPS)
                                                    │
                                                    └──► PostgreSQL
```

Backend layers (`backend/app`):

| Layer | Responsibility |
|-------|----------------|
| `api/routers` | HTTP only: parse input, call a service, return a schema. Auth is attached at router level. |
| `api/deps.py` | Dependency injection: DB session, current user, Keitaro client, URL guard. |
| `services/` | Business logic: campaign creation + compensation, offer distribution rules, auth, settings. |
| `integrations/keitaro` | The only place that talks HTTP to Keitaro: typed errors, retries, timeouts. |
| `repositories/` | Database access (SQLAlchemy 2.0 async). |
| `schemas/` | Pydantic v2 models for the API and for Keitaro objects. |
| `core/` | Config, security (crypto, JWT, passwords), SSRF guard, logging with secret redaction, error handlers. |

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/            # routers + dependencies
│   │   ├── core/           # config, security, url_guard, logging, exceptions
│   │   ├── db/             # engine, session, declarative base
│   │   ├── integrations/keitaro/   # async Admin API client + exceptions
│   │   ├── models/         # SQLAlchemy models
│   │   ├── repositories/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── cli.py          # python -m app.cli create-user|set-password
│   │   └── main.py
│   ├── alembic/versions/   # 0001 initial schema, 0002 auth + constraints
│   ├── tests/              # unit/API tests + tests/integration (real Keitaro, opt-in)
│   ├── Dockerfile, docker-entrypoint.sh, ruff.toml, requirements*.txt
├── frontend/               # React + TS + Vite
├── nginx/nginx.conf
├── docker-compose.yml
├── .env.example
├── .github/workflows/ci.yml
├── AUDIT_REPORT.md, CHANGELOG.md
```

## Prerequisites

* **Docker** 24+ with **Docker Compose v2** — for the one-command start, *or*
* **Python 3.12+**, **Node.js 22+**, **PostgreSQL 14+** — for local development.
* A Keitaro instance and an Admin API key (created in the Keitaro admin panel).

## Environment variables

Copy `.env.example` to `.env` and fill it in. Main variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | **yes** | — | ≥ 32 chars. JWT signing key and API-key encryption key are derived from it (HKDF). Changing it logs everyone out and makes the stored Keitaro key unreadable. |
| `POSTGRES_PASSWORD` | **yes** (Docker) | — | Database password. `POSTGRES_DB`, `POSTGRES_USER` default to `keitaro_manager` / `keitaro`. |
| `DATABASE_URL` | local dev | `postgresql+asyncpg://keitaro:keitaro@localhost:5432/keitaro_manager` | Built automatically in Docker. |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | no | — | Bootstrap user created at startup if it does not exist (password ≥ 10 chars, letters + digits). |
| `ACCESS_TOKEN_TTL_MINUTES` | no | `720` | Token lifetime. |
| `LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES` | no | `5`, `15` | Brute-force protection (per username; per IP the limit is 4×). |
| `KEITARO_API_URL`, `KEITARO_API_KEY` | no | — | Fallback connection if nothing is saved on the Settings page. |
| `KEITARO_TIMEOUT` | no | `15` | Seconds per request. |
| `KEITARO_RETRIES` | no | `2` | Retries for idempotent `GET` requests only. |
| `KEITARO_MAX_CONCURRENCY` | no | `8` | Parallel requests when loading streams of all campaigns. |
| `KEITARO_ALLOW_HTTP` | no | `false` | Allow `http://` tracker URLs (the API key would travel unencrypted). |
| `KEITARO_ALLOW_PRIVATE_HOSTS` | no | `false` | **Dev only.** Allow trackers on localhost/private networks. Cloud-metadata addresses stay blocked. |
| `CORS_ORIGINS` | no | `http://localhost:5173` | Comma-separated origins, only needed when the SPA is served from another origin. |
| `APP_PORT` | no | `8080` | Host port of nginx. |

## Quick start with Docker

```bash
cp .env.example .env
```

Edit `.env`: set `SECRET_KEY`, `POSTGRES_PASSWORD` and `ADMIN_PASSWORD`. A random secret:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Start everything (PostgreSQL → migrations → backend → nginx/frontend):

```bash
docker compose up -d --build
```

Open <http://localhost:8080>, log in with `ADMIN_USERNAME` / `ADMIN_PASSWORD`, go to **Settings**, enter the Keitaro
URL and API key, press **Check connection**, then **Save**.

Useful commands:

```bash
docker compose ps
```

```bash
docker compose logs -f backend
```

```bash
docker compose exec backend python -m app.cli create-user alice
```

```bash
docker compose down
```

Data lives in the `postgres_data` volume (`docker compose down -v` deletes it). The backend container runs
`alembic upgrade head` on every start (`backend/docker-entrypoint.sh`), so it is always on the latest schema. Health
checks: PostgreSQL (`pg_isready`), backend (`GET /api/health`), frontend (nginx). The backend starts only after the
database is healthy and nginx only after the backend is healthy.

## Local development without Docker

Backend:

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+asyncpg://keitaro:keitaro@localhost:5432/keitaro_manager
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
alembic upgrade head
python -m app.cli create-user admin
uvicorn app.main:app --reload --port 8000
```

(Keep `SECRET_KEY` stable between runs — put it in `backend/.env`, which is git-ignored and read automatically.)

Frontend (proxies `/api` to `http://localhost:8000`; override with `VITE_PROXY_TARGET`):

```bash
cd frontend
npm ci
npm run dev
```

Open <http://localhost:5173>.

## Database migrations

Migrations live in `backend/alembic/versions` and are applied with Alembic; `DATABASE_URL` is read from the
environment (`alembic/env.py`).

| Revision | Content |
|----------|---------|
| `0001` | `campaigns`, `campaign_logs`, `keitaro_config` |
| `0002` | `users`, `login_attempts`, `campaign_logs.user_id` (FK → users, `ON DELETE SET NULL`), CHECK constraints |

```bash
cd backend
alembic upgrade head          # apply all migrations
alembic current               # show the current revision
alembic downgrade -1          # roll back one migration
alembic check                 # verify models and migrations are in sync
alembic revision --autogenerate -m "describe change"   # create a new migration after changing models
```

In Docker: `docker compose exec backend alembic current` (migrations are applied automatically on start; to run them
explicitly: `docker compose run --rm backend alembic upgrade head`).

Both migrations were verified on a clean PostgreSQL 16 database: `upgrade head` → `check` (no drift) →
`downgrade base` → `upgrade head`. CI repeats this on every push.

## Running tests and checks

```bash
cd backend
pytest -q                     # 178 tests, SQLite in memory + httpx.MockTransport, no network needed
ruff check app tests alembic
```

```bash
cd frontend
npm run lint && npm run typecheck && npm run build
```

What the backend suite covers:

| File | Scope |
|------|-------|
| `test_campaign_creator.py` | exact payloads sent to Keitaro, stream order, invalid GEO/offer/domain/group/source, failure on campaign / stream 1 / stream 2 / DB save, rollback and incomplete-rollback reporting, `campaign_id` verification |
| `test_campaign_editor.py` | list/add/duplicate/remove/remove-last, manual/equal/normalized distribution, invalid splits, inactive offers, multiple streams, partial-failure compensation, concurrent edit detection |
| `test_auth.py` | 401 on every protected endpoint, forged/expired/`alg=none` tokens, lockout and its expiry, password change, audit actor |
| `test_security.py` | SSRF (loopback, private, CGNAT, link-local, metadata, IPv6, IPv4-mapped, DNS → private, DNS rebinding), stored key never sent to another host, encryption at rest, log redaction |
| `test_keitaro_client.py` | HTTP status → exception mapping (400/401/403/404/422/429/5xx), GET-only retries, backoff, `Retry-After` |
| `test_api.py`, `test_distribution.py` | original end-to-end API flows and rounding helpers |

### Integration tests against a real Keitaro

The mocks prove our logic, not compatibility with your Keitaro version. `tests/integration/test_live_keitaro.py`
runs against a real instance and is skipped unless configured:

```bash
export KEITARO_IT_URL=https://tracker.example.com KEITARO_IT_API_KEY=...
pytest tests/integration -v                         # read-only: lists parse into our schemas
export KEITARO_IT_ALLOW_WRITE=1 KEITARO_IT_OFFER_ID=1 KEITARO_IT_OFFER_ID_2=2 \
       KEITARO_IT_DOMAIN_ID=1 KEITARO_IT_GROUP_ID=1 KEITARO_IT_SOURCE_ID=1
pytest tests/integration -v                         # + creates "it-xxxx" campaign, edits offers, archives it
```

Use a test instance. In CI the read-only part runs when the `KEITARO_IT_URL` / `KEITARO_IT_API_KEY` repository
secrets are set.

## API documentation

Interactive OpenAPI docs: <http://localhost:8080/api/docs> (ReDoc: `/api/redoc`). Click **Authorize** and paste the
`access_token` from `POST /api/auth/login`.

| Method & path | Description |
|---------------|-------------|
| `GET /api/health` | Public. DB status, whether Keitaro is configured. |
| `POST /api/auth/login` | Public. `{username, password}` → `{access_token, expires_at, user}`. |
| `GET /api/auth/me`, `POST /api/auth/password` | Current user, change password. |
| `GET /api/campaigns` | List (`search`, `group_id`, `state`, `with_offers`). |
| `POST /api/campaigns` | **Campaign Creator.** `{name, country, offer_id, domain_id, group_id, traffic_source_id}`. |
| `GET / PUT / DELETE /api/campaigns/{id}` | Detail with streams and offers / update / archive. |
| `GET /api/campaigns/{id}/offers` | Offers of all offer streams + per-stream totals. |
| `POST /api/campaigns/{id}/offers` | Add offer `{offer_id, stream_id?, share?}`. |
| `PUT /api/campaigns/{id}/offers` | Replace a stream's offers `{stream_id, offers:[{offer_id, share, state}], expected_offer_ids?}`. |
| `POST /api/campaigns/{id}/offers/distribute` | `{stream_id, mode: "equal" \| "normalize"}`. |
| `DELETE /api/campaigns/{id}/offers/{offer_id}?stream_id=` | Remove from one stream or from all. |
| `GET / POST /api/campaigns/{id}/streams` | Streams of a campaign / create. |
| `GET / PUT / DELETE /api/streams/{id}`, `POST /api/streams/{id}/enable\|disable` | Stream management. |
| `GET /api/resources/{domains\|groups\|sources\|offers}` | Keitaro reference data. |
| `GET / PUT /api/settings`, `POST /api/settings/test` | Keitaro connection. |
| `GET /api/logs` | Audit log (`campaign_id`, `limit`). |

Errors always have the shape `{"detail": "...", "code": "...", ...}`; validation errors add
`errors: [{field, message}]`, failed multi-step operations add `rollback: {performed, ok, steps[]}`.

| Code | HTTP | Meaning |
|------|------|---------|
| `not_authenticated`, `invalid_token`, `invalid_credentials` | 401 | Our own authentication. |
| `too_many_attempts` | 429 | Login locked; see `Retry-After`. |
| `validation_error` | 422 | Input or business rule violated. |
| `duplicate_offer`, `stale_stream` | 409 | Offer already in stream / stream changed meanwhile. |
| `unsafe_url` | 422 | Keitaro URL rejected by the SSRF guard. |
| `keitaro_not_configured` | 400 | No URL/key saved. |
| `keitaro_auth_failed` | 502 | Keitaro rejected the API key (deliberately not 401). |
| `keitaro_rejected` / `keitaro_not_found` | 422 / 404 | Keitaro 400/422 / 404. |
| `keitaro_rate_limited` | 429 | Keitaro 429. |
| `keitaro_server_error`, `keitaro_unavailable`, `keitaro_timeout` | 502 / 502 / 504 | Keitaro 5xx / network / timeout. |
| `operation_failed`, `partial_update_failed`, `persistence_failed` | varies | Multi-step operation failed and was compensated. |

## Keitaro API configuration

* **URL** — the tracker address, e.g. `https://tracker.example.com`; `/admin_api/v1` is appended automatically.
  Must be `https` and publicly routable (see [Security](#security-considerations)).
* **API key** — sent in the `Api-Key` header. Stored encrypted; the UI only shows `ab••••••yz`.
* When changing the URL the key must be entered again — the stored key is never sent to a different host.
* Endpoints used: `GET/POST /campaigns`, `GET/PUT/DELETE /campaigns/{id}`, `POST /campaigns/{id}/enable|disable`,
  `GET /campaigns/{id}/streams`, `POST /streams`, `GET/PUT/DELETE /streams/{id}`, `POST /streams/{id}/enable|disable`,
  `GET /offers`, `GET /offers/{id}`, `GET /domains`, `GET /groups?type=…`, `GET /traffic_sources`.
* Retries: only `GET`, on timeouts, connection errors, 429, 502, 503, 504; exponential backoff (0.5 s, 1 s, …,
  capped at 10 s) or `Retry-After`. `POST/PUT/DELETE` are never retried, so a timeout can never create a duplicate.

## Campaign Creator

**Campaigns → Create campaign**. Fields: *Campaign name*, *Country / GEO* (ISO-3166 alpha-2), *Offer*, *Domain*,
*Group*, *Traffic source* — lists are loaded from Keitaro.

What is created in Keitaro:

| Object | Settings |
|--------|----------|
| Campaign | `name`, random 8-char `alias`, `type: position`, `state: active`, `domain_id`, `group_id`, `traffic_source_id` |
| Stream 1 — **GEO Redirect** | `type: regular`, `position: 1`, `state: active`, `schema: redirect`, `action_type: http`, `action_payload: https://www.google.com` (configurable "safe URL"), filter `country` / `accept` / `[XX]`, `collect_clicks: true` |
| Stream 2 — **Offers** | `type: regular`, `position: 2`, `state: active`, `schema: landings`, no filters, `offers: [{offer_id, share: 100, state: active}]` |

Why this routes correctly: a campaign of type `position` evaluates its *regular* streams in position order and sends the
visitor to the first stream whose filters match. Visitors from `XX` match stream 1 and go to Google; nobody else matches
it, and stream 2 has no filters, so it receives all remaining traffic.

Order of operations and rollback:

1. Validate input and check in Keitaro that offer, domain, group and source exist (nothing is written if not).
2. `POST /campaigns` → `POST /streams` (GEO) → `POST /streams` (Offers); each stream's `campaign_id` is verified.
3. Save the local record and commit.
4. If any of 2–3 fails: delete the created streams (newest first), then the campaign (Keitaro moves it to the
   archive), roll back the DB transaction, write an `error` audit entry with the rollback report and return an error
   that says what was undone — or which objects need manual cleanup if Keitaro also refused the deletion.

## Campaign Editor

**Campaigns → open a campaign**. The *Offers & traffic distribution* card shows the offers of an offer stream
(`schema: landings`); with several offer streams a selector appears.

* **Add offer** — choose an offer; leave *share* empty to split equally between all active offers, or enter a share
  (1–100) to pin it and scale the others proportionally into the remainder.
* **Remove offer** (with confirmation) — the remaining active offers are scaled back to 100 %. The last offer and the
  last active offer cannot be removed.
* **Manual split** — edit percentages, toggle offers on/off. *Split equally* and *Normalize to 100 %* recompute
  locally; **Save** is enabled only when the active offers total exactly 100 %.
* Disabled offers keep their stored share but are ignored in the total and receive no traffic.

Rounding: integer shares, computed with the largest-remainder method, so totals are always exactly 100
(`3 offers → 34/33/33`, `70/30 + new 20 % → 56/24/20`).

Every write is validated on the backend again (sum = 100, ≥ 1 active, no duplicates, offers exist in Keitaro). The
client sends the offer ids it saw; if the stream was changed elsewhere in the meantime the save is refused with 409
and the UI reloads. When one operation touches several streams (removing an offer from all streams) and one update
fails, the already-changed streams are restored to their previous offers.

## Security considerations

* **Authentication** — all endpoints except health and login require `Authorization: Bearer <JWT>` (HS256, signed with
  an HKDF-derived key, `exp`/`iat`/`iss` required, `alg=none` rejected). Users are checked on every request, so
  deactivating a user takes effect immediately.
* **Passwords** — scrypt (n=2¹⁴, r=8, p=1, 16-byte salt), constant-time comparison; unknown users take the same time.
* **Brute force** — after 5 failed logins for a username (20 per IP) within 15 minutes the login returns 429 with
  `Retry-After`. Attempts are stored in the DB, so the limit holds across restarts and workers.
* **Keitaro API key** — encrypted at rest with Fernet (AES-CBC + HMAC), key derived from `SECRET_KEY`; never returned
  by the API; masked in the UI; registered with the log filter that replaces it (and any `Api-Key:`, `Authorization:`,
  `password=` values) with `***`.
* **SSRF** — the tracker URL must be `https`, without credentials/query, and every resolved IP must be public:
  loopback, RFC 1918, CGNAT, link-local, ULA, multicast, reserved, IPv4-mapped variants and metadata host names are
  rejected. The check runs on save and before every use (DNS changes). Redirects are not followed.
  Cloud-metadata ranges are blocked even with `KEITARO_ALLOW_PRIVATE_HOSTS=true`.
* **CORS** — explicit origin list, limited methods/headers, no credentials. It is *not* used as access control.
* **Headers** — nginx sends CSP, `X-Frame-Options`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`; API
  responses are `no-store`.
* **Containers** — backend runs as non-root, read-only root FS, `no-new-privileges`; the backend port is not published;
  nginx overwrites `X-Forwarded-For` so clients cannot spoof the IP used by the login limiter.
* **Errors** — internal exceptions return a generic message; details are only in server logs.
* **Secrets** — nothing secret is committed; `.env` is git-ignored; compose refuses to start without `SECRET_KEY`
  and `POSTGRES_PASSWORD`.

Token storage trade-off: the SPA keeps the token in `sessionStorage` (cleared when the tab closes). This avoids CSRF
entirely but means an XSS bug could read it; the strict CSP mitigates that. An httpOnly-cookie session with CSRF
tokens would be the next step for a multi-user production deployment.

## Known limitations

* The Keitaro Admin API documentation was not reachable from the development environment and no live Keitaro was
  available, so compatibility was verified against an emulator. Points to confirm on a real instance (the integration
  tests do exactly this): the `type` value of `GET /groups` (the client tries `campaign`, then `campaigns`), the exact
  response of `DELETE /campaigns/{id}` (archive), and that `PUT /streams/{id}` with `offers` replaces the list.
* Concurrency control is optimistic and per-stream (offer ids), Keitaro itself offers no versioning.
* The campaigns list loads streams for every campaign (N+1, bounded by `KEITARO_MAX_CONCURRENCY`); for thousands of
  campaigns use `with_offers=false`.
* Single role: every user is an administrator.
