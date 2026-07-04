# XyaPanel

Licensing panel system for generating, distributing, and validating software license keys.

**Stack:** Python 3.12+ · FastAPI · SQLite (aiosqlite) · Celery + Redis · React + Vite (admin + reseller dashboards)

## Features

- **License Key Generation** — cryptographically strong keys (UUID4-based), HWID binding on first activation, configurable expiry durations
- **Async Watermarking** — Celery background task watermarks APK (ZIP) and .so (ELF) binaries per license
- **Live Validation** — every license check is a live DB lookup; no offline validation, no signed tokens
- **Heartbeat System** — 10-minute client heartbeat with APScheduler-based missed-heartbeat detection and auto-pause
- **Reseller System** — invite-code registration, monetary balance, stock-based inventory, store purchases, key generation from stock
- **Full Ledger Audit** — immutable transaction log for every balance-affecting event (credits, purchases, refunds)
- **AES-256-GCM Encryption** — application-layer payload encryption on top of HTTPS/TLS, with HKDF per-session key derivation
- **Three Role Auth** — admin (JWT), reseller (JWT), client (session-based) with role enforcement at the data-access layer
- **NoSQL Injection Protection** — input sanitization middleware blocks `$` operators and null bytes
- **Rate Limiting** — IP-based rate limiting on the validation endpoint (30 req/60s)

## Setup

### Prerequisites

- Python 3.12+
- Redis (for Celery broker)
- Node.js 18+ (for the dashboard frontend)
- (Optional) Celery worker for watermarking

### 1. Clone

```bash
git clone https://github.com/brandonmathewp/XyaPanel.git
cd XyaPanel
```

### 2. Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set:

| Variable | Description |
|---|---|
| `DB_NAME` | SQLite database file name (default: `xya_panel`) |
| `REDIS_URL` | Redis broker URL (default: `redis://localhost:6379/0`) |
| `MASTER_SECRET` | 64-char hex string for HKDF key derivation |
| `JWT_SECRET` | 64-char hex string for JWT signing |
| `ADMIN_EMAIL` | Bootstrap admin email |
| `ADMIN_PASSWORD_HASH` | bcrypt hash of admin password |

Generate secrets:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Generate admin password hash (use a heredoc to avoid shell history expansion issues with `!` and other special characters):
```bash
python3 << 'EOF'
import bcrypt
print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())
EOF
```

### 4. Start Redis

Celery requires a Redis broker. Install and start it if you haven't already:

```bash
sudo apt-get install -y redis-server
redis-server --daemonize yes
```

Verify it's running:

```bash
redis-cli ping   # should return PONG
```

### 5. Run the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API is now available at `http://localhost:8000` and the Swagger docs at `http://localhost:8000/docs`.

### 6. (Optional) Run Celery worker for watermarking

```bash
celery -A app.tasks.celery_app worker --loglevel=info
```

### 7. Run the dashboard

The React admin/reseller dashboard runs on port 3000 and proxies `/api/*` requests to the backend at `:8000`.

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` — log in as admin or reseller.

To build for production:

```bash
cd frontend
npm run build   # outputs to frontend/dist/
```

## API Summary

### Health
- `GET /health` — server health check

### Auth
- `POST /auth/admin/login` — admin login (returns JWT)
- `POST /auth/reseller/login` — reseller login
- `POST /auth/reseller/register` — reseller registration (invite code required)
- `POST /auth/admin/invite-codes/generate` — admin generates invite codes
- `GET /auth/admin/invite-codes` — admin lists invite codes
- `POST /auth/client/version-check` — client APK version check (unencrypted)
- `POST /auth/client/login` — client full login + session establishment

### Licenses
- `POST /licenses/validate` — client validates/activates license (rate-limited)
- `POST /licenses/admin/generate` — admin generates license
- `GET /licenses/admin/list` — admin lists licenses (filterable)
- `GET /licenses/admin/{key}` — admin fetches single license
- `POST /licenses/admin/{key}/revoke` — admin revokes license
- `POST /licenses/admin/{key}/pause` — admin pauses license
- `POST /licenses/admin/{key}/resume` — admin resumes paused license

### Products (Admin)
- `POST /products/admin` — create product
- `GET /products/admin` — list products
- `GET /products/admin/{id}` — get product
- `PUT /products/admin/{id}` — update product
- `DELETE /products/admin/{id}` — delete product (blocked if licenses exist)
- `POST /products/admin/{id}/upload-apk` — upload APK artifact
- `POST /products/admin/{id}/upload-so` — upload .so artifact
- `GET /products/store` — public store listing

### Heartbeat
- `POST /heartbeat` — client heartbeat (authenticated)

### Reseller
- `GET /reseller/store` — browse store
- `POST /reseller/store/purchase` — purchase stock
- `POST /reseller/generate-key` — generate key from stock
- `GET /reseller/keys` — list own keys
- `GET /reseller/ledger` — transaction history
- `POST /reseller/admin/credit` — admin credits reseller balance

## Project Structure

```
XyaPanel/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── core/
│   │   ├── config.py        # pydantic-settings env config
│   │   ├── database.py      # SQLite aiosqlite connection
│   │   ├── encryption.py    # AES-256-GCM + HKDF utilities
│   │   └── security.py      # Auth deps, rate limiting, NoSQL sanitization
│   ├── models/
│   │   ├── license.py       # License document + schemas
│   │   ├── auth.py          # Admin, reseller, invite code, session models
│   │   ├── product.py       # Product document + schemas
│   │   └── reseller.py      # Stock, ledger, purchase/key-gen schemas
│   ├── routers/
│   │   ├── license.py       # License endpoints
│   │   ├── auth.py          # Auth endpoints
│   │   ├── product.py       # Product endpoints
│   │   ├── heartbeat.py     # Heartbeat endpoint
│   │   ├── reseller.py      # Reseller endpoints
│   │   └── dependencies.py  # Auth dependency re-exports
│   ├── services/
│   │   ├── license_service.py
│   │   ├── auth_service.py
│   │   ├── product_service.py
│   │   ├── heartbeat_service.py
│   │   ├── reseller_service.py
│   │   └── (watermark_service.py — TBD)
│   └── tasks/
│       ├── celery_app.py    # Celery app config
│       └── watermark.py     # Watermarking task
├── frontend/                # Mobile dashboard (React, TBD)
├── tests/                   # Smoke tests
├── requirements.txt
├── .env.example
├── .gitignore
├── CHANGELOG.md
└── README.md
```

## Operational Notes

### Admin Bootstrap

On first startup, if no admin account exists in the `admins` collection, the server automatically creates one from `ADMIN_EMAIL` and `ADMIN_PASSWORD_HASH` in `.env`.

### SQLite Notes

- SQLite is serverless — the entire database is a single `.db` file in the project directory. No external database server required.
- WAL journal mode is enabled for concurrent read/write performance.
- Artifact files (APK/.so) are stored on disk in the `artifacts/` directory, keeping the database small.
- The reseller purchase and key-generation flows use saga-style compensating actions (no multi-document transactions needed).
- **In-memory rate limiting**: The rate limiter is process-local. For multi-worker deployments, replace with a Redis-backed implementation.

### Heartbeat Background Job

The heartbeat sweep runs every 60 seconds via APScheduler within the FastAPI process. For horizontal scaling, consider a dedicated scheduler worker or use Celery Beat.

### Encryption

- All endpoints except `/auth/client/version-check` use AES-256-GCM application-layer encryption on top of HTTPS/TLS.
- Session keys are derived via HKDF from the server's `MASTER_SECRET` and bound to the license key + HWID.
- Wire format: `hex(nonce || ciphertext || tag)` — a single hex string.

## License Durations

Supported durations (fixed enum): `2_hours`, `1_day`, `3_days`, `1_week`, `1_month`, `2_months`, `6_months`, `1_year`, `lifetime`
