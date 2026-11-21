# Audit Report — Keitaro Manager

Date: 2026-11-21 · Scope: whole repository at commit `b30f260` (backend, frontend, infra, docs).

## 0. How the audit was performed

* Read every backend module (`app/**`, `alembic/**`, `tests/**`) and every frontend module (`src/**`).
* Ran the existing test-suite: **14 passed**.
* Applied migration `0001` on a clean PostgreSQL 16 database, ran `alembic check` (models and migration are in sync) and `alembic downgrade base` — all OK.
* `npm ci && npm run build` for the frontend — OK (no lint configured).
* `ruff check` — 18 style findings (imports order, unused names), no runtime bugs.
* **Not verified:** the official Keitaro Admin API documentation host (`admin-api.docs.keitaro.io`) is not reachable from the
  audit environment, and no real Keitaro instance was available. Every statement below about the Keitaro API is based on
  the existing client code and general knowledge of Admin API v1 and is marked *unverified* where it matters.

Overall: the project already has a sensible layered structure (routers → services → repositories / Keitaro client),
typed Pydantic schemas, an audit log and decent tests. The serious problems are in **security** (no authentication,
SSRF + API-key exfiltration) and **failure handling** (incomplete compensation). The rest are improvements.

## 1. Findings

Priority: **P0** critical · **P1** high · **P2** medium · **P3** low.

### Security

| # | Prio | Finding | Where |
|---|------|---------|-------|
| S1 | P0 | **No authentication at all.** Every endpoint is public, including `PUT /api/settings` (changes the Keitaro URL/key), campaign deletion and stream editing. CORS is the only "protection", and CORS does not protect against non-browser clients. | `app/api/**` |
| S2 | P0 | **SSRF.** `PUT /settings` and `POST /settings/test` accept any `http(s)` URL: `localhost`, private ranges, `169.254.169.254` (cloud metadata) etc. The test endpoint returns the error text, so it works as an internal port scanner. | `schemas/settings.py`, `services/settings_service.py` |
| S3 | P0 | **Stored API key exfiltration.** `POST /settings/test` with only `api_url` uses the *stored* key: `api_key = data.api_key or conn.api_key`. Anyone can send the real Keitaro key to a host they control. | `settings_service.test_connection` |
| S4 | P1 | No brute-force protection (there is no login yet; must be part of S1 fix). | — |
| S5 | P2 | One `SECRET_KEY` is used directly (`sha256(SECRET_KEY)`) as the Fernet key. Once JWTs are added the same key material would be reused for signing. Keys must be domain-separated (HKDF). Existing ciphertexts must stay readable. | `core/security.py` |
| S6 | P2 | No log redaction. The client never logs the key, but nothing prevents a future `logger.info(headers)`/exception repr from leaking it. | `core/logging.py` |
| S7 | P2 | `.env.example` is referenced by `docker-compose.yml` and `.gitignore` but does not exist; `.gitignore` contains a meaningless `!../.env.example` rule. | root |
| S8 | P3 | nginx has no `Content-Security-Policy`/`Permissions-Policy` headers. | `nginx/nginx.conf` |
| S9 | P3 | `uvicorn --forwarded-allow-ips "*"` — acceptable only because the backend port is not published (only nginx can reach it). Needs to be documented since per-IP rate limiting relies on `X-Forwarded-For`. | `backend/Dockerfile` |

### Keitaro integration

| # | Prio | Finding |
|---|------|---------|
| K1 | P1 | No retry at all. Transient `429/502/503/504`/timeouts fail immediately. Retries must be limited to idempotent reads (`GET`) — retrying `POST /campaigns` could create duplicates. |
| K2 | P2 | `429` (rate limit), `400/422` (validation) and `5xx` are not distinguished: all become `KeitaroAPIError`. `Retry-After` is ignored. |
| K3 | P2 | `GET /groups?type=campaign` — the exact enum value of `type` is **unverified** (some Keitaro versions document `campaigns`). If the value is wrong the creator cannot load groups. |
| K4 | P3 | `DELETE /campaigns/{id}` moves a campaign to the Keitaro archive (not a hard delete) — fine for rollback but must be documented. *Unverified against docs.* |
| K5 | P3 | `list_campaigns` loads streams of every campaign (N+1). It is bounded by a semaphore (`KEITARO_MAX_CONCURRENCY`) — acceptable, documented. |

### Campaign Creator

| # | Prio | Finding |
|---|------|---------|
| C1 | P1 | **DB persistence failure is not compensated.** If `repo.create()`/`commit()` fails after Keitaro succeeded, the campaign and both streams stay in Keitaro while the API returns 500 — the user retries and gets duplicates. |
| C2 | P1 | **Stream rollback is incomplete.** When stream #2 fails, only the campaign is deleted; stream #1 is left as is. Rollback failures are only logged, the response does not say that manual cleanup is needed. |
| C3 | P2 | Domain, group and traffic source are not validated before writing to Keitaro; an invalid id surfaces as an opaque Keitaro error *after* partial creation. Only the offer is checked. |
| C4 | P2 | The `campaign_id` of created streams is not verified. |
| C5 | P3 | Stream names were `GEO XX → url` / `Offers`; the spec requires `GEO Redirect` / `Offers`. |
| C6 | ✔ | Stream order is correct: campaign `type=position`, GEO stream `position=1` with `country accept [XX]`, offer stream `position=2` without filters. Keitaro evaluates *regular* streams by position and takes the first whose filters match, so visitors from XX go to Google and everyone else falls through to the offer stream. |

### Campaign Editor / traffic distribution

| # | Prio | Finding |
|---|------|---------|
| E1 | P1 | **No compensation for multi-stream removal.** `remove()` updates several streams sequentially; if the 2nd update fails the 1st stream is already changed. |
| E2 | P1 | **Invalid states allowed:** `PUT /offers` (and stream create/update) accept a list where *all* offers are disabled. `validate_offer_shares` returns OK when there is no active offer, so a stream can be saved that sends traffic nowhere. |
| E3 | P2 | `PUT /offers` does not check that the submitted offer ids exist in Keitaro, nor whether offers are added/removed implicitly. |
| E4 | P2 | `CampaignOffersUpdate.stream_id` is required, but `_pick_stream` silently falls back to "first stream" logic when `None` — dead branch, fine. |
| E5 | P3 | Distribution operations (equal / normalise) exist only on the frontend; the backend has no endpoint, so API clients cannot reuse the rounding logic. |
| E6 | ✔ | `equal_split` and `scale_to_total` (largest-remainder) are correct and always sum to 100. |

### Database

| # | Prio | Finding |
|---|------|---------|
| D1 | P2 | No `CHECK` constraints (`campaign_logs.status`, `campaigns.country` length/format). |
| D2 | P2 | Audit log has no actor — after adding users, logs must reference `users.id` (FK, `ON DELETE SET NULL`). |
| D3 | P3 | `alembic/__init__.py` and `alembic/versions/__init__.py` make the migrations folder a package named `alembic`, which can shadow the real `alembic` library on `sys.path` (works today only because the CLI imports the library first). |
| D4 | ✔ | Migration 0001 applies on a clean DB, `alembic check` reports no drift, downgrade works. |

### Frontend

| # | Prio | Finding |
|---|------|---------|
| F1 | P0 | No login screen / token handling (follows from S1). |
| F2 | P2 | No ESLint, no `lint` script; CI cannot check code style. |
| F3 | P3 | Errors with code `keitaro_rate_limited` / `unauthorized` etc. not handled specially. |
| F4 | ✔ | All buttons call real endpoints; shares on screen are rendered from Keitaro responses. |

### DevOps / docs / tests

| # | Prio | Finding |
|---|------|---------|
| O1 | P1 | README is empty (one line). No migration / startup instructions — this is a hard requirement of the assignment. |
| O2 | P2 | No CI (GitHub Actions). |
| O3 | P2 | No linters configured for Python. |
| O4 | P2 | Tests do not cover: rollback when stream #1 fails, DB failure compensation, partial update failure, SSRF, auth, invalid domain/group/source, duplicate offers, inactive offers, multiple streams. |
| O5 | P2 | No integration tests against a real Keitaro instance. |

## 2. Fix plan (executed in this order)

1. **Security core:** users table + scrypt password hashing, JWT (HS256, HKDF-derived key), `/auth/login` with
   DB-backed brute-force lockout, `get_current_user` dependency on every router except `/health` and `/auth/login`;
   CLI + env bootstrap for the first admin. (S1, S4, F1)
2. **SSRF guard** for the Keitaro URL — scheme allow-list, no credentials in URL, DNS resolution with rejection of
   loopback/private/link-local/reserved/multicast and metadata hosts; applied on save *and* before every client build
   (DNS rebinding). Test endpoint never sends the stored key to a different URL. (S2, S3)
3. HKDF key separation with legacy-key fallback, log redaction filter, `.env.example`. (S5–S7)
4. **Keitaro client:** typed error hierarchy (validation / rate-limit / server), GET-only retry with backoff and
   `Retry-After`, structured logging, groups `type` fallback. (K1–K3)
5. **Campaign Creator:** pre-validation of offer/domain/group/source, stream `campaign_id` verification, full
   compensation (streams → campaign) on Keitaro *and* DB failures, rollback report in the error. (C1–C5)
6. **Editor:** forbid "no active offers", validate offer ids, compensation for multi-stream updates, backend
   distribution endpoint. (E1–E3, E5)
7. **DB:** migration `0002` — `users`, `login_attempts`, `campaign_logs.user_id` FK, CHECK constraints; remove the
   `__init__.py` files from the migrations folder. (D1–D3)
8. **Frontend:** login page, token storage + 401 handling, user menu/logout, ESLint, error codes. (F1–F3)
9. **Tests:** full matrix from the assignment + opt-in live integration tests. (O4, O5)
10. **DevOps & docs:** CI workflow, ruff config, compose hardening, README, CHANGELOG. (O1–O3, S8)

The status of each item after the work is recorded in `CHANGELOG.md`.

## 3. Status after the work

All findings S1–S9, K1–K3, C1–C5, E1–E3, E5, D1–D3, F1–F3 and O1–O5 were addressed; see `CHANGELOG.md` for details.
K4 and K5 are documented (README → *Known limitations*). Additional issue found during end-to-end testing and fixed:
the development flag `KEITARO_ALLOW_PRIVATE_HOSTS` must not unblock cloud-metadata addresses — they are now blocked in
every mode.

Still **unverified** (needs a real Keitaro, covered by `tests/integration`): `GET /groups` type value, behaviour of
`DELETE /campaigns/{id}`, replacement semantics of `PUT /streams/{id}` with `offers`, and the exact JSON shapes
returned by the user's Keitaro version.
