# Changelog

## 1.1.0 — 2026-11-21 · Production-readiness pass

Based on the findings in [AUDIT_REPORT.md](AUDIT_REPORT.md) (finding ids in brackets).

### Security
- **Authentication** for the whole API: `users` table, scrypt password hashing, JWT (HS256) access tokens,
  `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/password`. Only `/api/health` and `/api/auth/login`
  are public. [S1]
- **Brute-force protection**: DB-backed `login_attempts`, lockout per username (5 / 15 min) and per IP (20 / 15 min),
  `429` + `Retry-After`; constant-time behaviour for unknown users. [S4]
- **SSRF guard** for the Keitaro URL: https-only by default, no credentials/query, DNS resolution with rejection of
  loopback/private/CGNAT/link-local/ULA/multicast/reserved/IPv4-mapped addresses and internal/metadata host names;
  re-checked before every use; metadata ranges blocked even in the dev "private hosts" mode. [S2]
- **Stored API key can no longer be sent to another host**: changing the URL requires re-entering the key, and the
  connection test with a new URL requires a key. [S3]
- HKDF-separated keys for JWT signing and secret encryption; v1.0 ciphertexts remain readable and are re-encrypted on
  the next save. `SECRET_KEY` minimum length raised to 32. [S5]
- Log redaction filter (known secrets, `Api-Key`, `Authorization`, `password`). [S6]
- `.env.example` added, `.gitignore` fixed; compose requires `SECRET_KEY` and `POSTGRES_PASSWORD`. [S7]
- nginx: CSP and Permissions-Policy headers, `X-Forwarded-For` overwritten instead of appended. [S8, S9]
- CORS limited to the methods/headers actually used; API responses are `Cache-Control: no-store`.
- Backend container: read-only root FS, tmpfs `/tmp`, `no-new-privileges`.

### Keitaro integration
- New typed errors: `KeitaroValidationError` (400/422), `KeitaroRateLimitError` (429, `retry_after`),
  `KeitaroServerError` (5xx); 3xx answers are errors (redirects are never followed). [K2]
- Retries **only for `GET`** on timeouts, connection errors, 429/502/503/504 with exponential backoff and
  `Retry-After` (capped at 10 s); configurable `KEITARO_RETRIES`. [K1]
- `GET /groups` tries `type=campaign`, then `type=campaigns`. [K3]
- Connection-pool limits, `User-Agent`, structured `extra` fields in request logs.

### Campaign Creator
- Offer, domain, group and traffic source are validated against Keitaro **before** anything is created; all invalid
  fields are reported together with field names. [C3]
- Full compensation: on failure of stream 1, stream 2 **or the database save**, created streams and the campaign are
  deleted; the response (`rollback`) and the audit log say what was undone or what needs manual cleanup. [C1, C2]
- The `campaign_id` of each created stream is verified. [C4]
- Stream names `GEO Redirect` / `Offers`. [C5]

### Campaign Editor
- A stream can no longer be saved without an active offer. [E2]
- `PUT /offers` checks that new offer ids exist in Keitaro. [E3]
- Optimistic concurrency: `expected_offer_ids` → `409 stale_stream` if the stream changed meanwhile.
- Multi-stream updates restore already-changed streams if a later update fails (`partial_update_failed`). [E1]
- New `POST /api/campaigns/{id}/offers/distribute` (`equal` / `normalize`). [E5]
- Adding an offer that is already in the stream returns **409 `duplicate_offer`** (was 422).

### Database
- Migration `0002`: `users`, `login_attempts`, `campaign_logs.user_id` FK (`ON DELETE SET NULL`), CHECK constraints
  on `campaign_logs.status`, `campaigns.country`, `campaigns.offer_id`. [D1, D2]
- Removed `__init__.py` from `alembic/` and `alembic/versions/` (shadowed the `alembic` package). [D3]
- Audit log entries record the acting user.

### Frontend
- Login page, protected routes, token in `sessionStorage`, automatic logout on 401, user + logout in the sidebar,
  password change on the Settings page. [F1]
- Offers manager sends `expected_offer_ids`, reloads on 409, blocks saving without an active offer.
- Campaign Creator shows the rollback report of a failed creation.
- Settings page maps field errors from the API and asks for the key when the URL changes.
- ESLint (flat config, typescript-eslint, react-hooks) with `npm run lint`. [F2]

### Tooling, tests, docs
- Tests: 14 → **178** (+3 opt-in live Keitaro tests). New suites for creator, editor, auth, security, client. [O4, O5]
- Ruff configuration (`backend/ruff.toml`). [O3]
- GitHub Actions: ruff, migrations on PostgreSQL (upgrade/check/downgrade/upgrade), pytest, eslint, tsc, vite build. [O2]
- CLI: `python -m app.cli create-user|set-password`; optional bootstrap admin from env.
- README rewritten; `AUDIT_REPORT.md`, `CHANGELOG.md` added. [O1]

### Breaking changes
- All endpoints except health/login now require a token.
- `SECRET_KEY` must be ≥ 32 characters.
- Duplicate offer: 409 instead of 422. Saving a stream whose offers are all disabled: 422.
- `POSTGRES_PASSWORD` has no default in docker-compose anymore.

## 1.0.0
- Initial version: Campaign Creator, campaigns list, offers/streams editor, resources, settings, audit log.
