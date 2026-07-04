# Changelog

All notable changes to XyaPanel will be documented in this file.

## [Unreleased]

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
