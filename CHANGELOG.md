# Changelog

All notable changes to XyaPanel will be documented in this file.

## [Unreleased]

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
