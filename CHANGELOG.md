# Changelog

All notable changes to XyaPanel will be documented in this file.

## [Unreleased]

### 2026-07-04 — Phase 4/8: Mobile Dashboards + Watermarking
- **Added:** Admin mobile dashboard (React + Vite) — license management, product management, invite codes, flagged license review
- **Added:** Reseller mobile dashboard — store browsing, stock purchase, key generation, keys list, ledger history
- **Added:** APK watermarking — HMAC-SHA256 embedded as ZIP comment (standard, non-disruptive)
- **Added:** .so watermarking — magic marker + HMAC appended at end-of-file (harmless to ELF loader)
- **Added:** Watermark extraction and verification for both APK and .so formats
- **Added:** Full Celery task integration — watermark enqueued on license generation (admin + reseller), auto-transitions pending → active
- **Added:** watermark_service.py with compute/verify/watermark/extract for APK and .so
- **Added:** Mobile-first CSS (max-width 430px, bottom nav, card layouts, bottom sheets, tap targets)

### 2026-07-04 — Phase 9: Finalization
- **Added:** Comprehensive README.md with setup, API summary, project structure, ops notes
- **Added:** Project-wide smoke tests (Phase 1 key-gen/expiry, Phase 2 password hashing/JWT)

### 2026-07-04 — Phase 7: Payload Encryption
- **Added:** AES-256-GCM encrypt/decrypt utilities
- **Added:** HKDF per-session key derivation from MASTER_SECRET
- **Added:** Consistent wire format: hex(nonce || ciphertext || tag)

### 2026-07-04 — Phase 6: Reseller Backend
- **Added:** Reseller models (stock, ledger, purchase/key-gen schemas)
- **Added:** Admin credit endpoint (balance credit with ledger entry)
- **Added:** Store purchase flow with saga-style compensating actions (M0 compatible)
- **Added:** Key generation from stock with saga-style rollback
- **Added:** Ledger service for immutable transaction audit trail
- **Added:** Reseller dashboard endpoints (store, purchase, keys, ledger)

### 2026-07-04 — Phase 5: Heartbeat System
- **Added:** Heartbeat endpoint (POST /heartbeat) with client session auth
- **Added:** Heartbeat service: verifies license+HWID, updates last_heartbeat_at, piggybacks features
- **Added:** APScheduler background job sweep every 60s for missed heartbeat detection
- **Added:** Auto-pause + flagged_for_review on missed heartbeat (11-min threshold)

### 2026-07-04 — Phase 3: Product Management
- **Added:** Product Pydantic models with duration pricing, version tracking, store flags
- **Added:** Product service (CRUD, artifact upload, delete precondition check)
- **Added:** Product admin router (create/edit/delete/list, APK/.so upload)
- **Added:** Public /products/store endpoint for reseller store browsing
- **Added:** Client version-check now queries product version config from DB
- **Added:** python-multipart dependency for file upload support

### 2026-07-04 — Phase 2: Authentication & Security
- **Added:** Admin auth — JWT-based login, single-account bootstrap from env config
- **Added:** Reseller auth — JWT login, invite-code registration flow
- **Added:** Invite code generation + listing (admin-only)
- **Added:** Client two-stage login: APK version check (unencrypted) + full login with session
- **Added:** Role-based auth dependencies (get_current_admin, get_current_reseller, get_current_client)
- **Added:** NoSQL injection sanitization middleware (blocks $operators, null bytes)
- **Added:** IP-based rate limiting on /licenses/validate (30 req/60s window)
- **Added:** Smoke tests for password hashing and JWT roundtrip
- **Changed:** Replaced passlib with direct bcrypt usage for compatibility
- **Changed:** Replaced admin auth stubs in license router with real JWT dependency

### 2026-07-04 — Phase 1: License Core
- **Added:** License Pydantic models with status/duration enums and validation schemas
- **Added:** License service layer (key generation, live-DB validation, HWID binding, status transitions)
- **Added:** License router (admin: generate/list/revoke/pause/resume; client: /validate)
- **Added:** Celery + Redis task queue with watermarking skeleton
- **Added:** Smoke tests for key generation and expiry logic
- **Changed:** Deprecated datetime.utcnow() → datetime.now(tz=timezone.utc) project-wide

### 2026-07-04 — Project Scaffolding (Phase 0)
- **Added:** Initial project structure with FastAPI skeleton
- **Added:** MongoDB Atlas connection via Motor (async driver)
- **Added:** Environment configuration via pydantic-settings
- **Added:** requirements.txt with core dependencies
- **Added:** .gitignore, .env.example
- **Added:** GitHub repository created and linked
