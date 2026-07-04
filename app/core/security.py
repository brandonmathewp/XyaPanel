"""Security module: auth dependencies, rate limiting, input sanitization."""

from __future__ import annotations

import re
from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from app.models.auth import UserRole
from app.services.auth_service import decode_jwt_token

# ---------------------------------------------------------------------------
# JWT bearer token extraction
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)


async def _extract_token(request: Request) -> str | None:
    """Extract Bearer token from Authorization header."""
    credentials: HTTPAuthorizationCredentials | None = await _bearer_scheme(request)
    if credentials is None:
        return None
    return credentials.credentials


# ---------------------------------------------------------------------------
# Role-based auth dependencies
# ---------------------------------------------------------------------------


async def get_current_admin(request: Request) -> dict[str, Any]:
    """FastAPI dependency: require valid admin JWT."""
    token = await _extract_token(request)
    if token is None:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    try:
        claims = decode_jwt_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if claims.get("role") != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")

    return claims


async def get_current_reseller(request: Request) -> dict[str, Any]:
    """FastAPI dependency: require valid reseller JWT."""
    token = await _extract_token(request)
    if token is None:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    try:
        claims = decode_jwt_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if claims.get("role") != UserRole.RESELLER:
        raise HTTPException(status_code=403, detail="Reseller access required")

    return claims


async def get_current_client(request: Request) -> dict[str, Any]:
    """FastAPI dependency: require valid client session.

    Client auth is session-based (not JWT). The session ID is passed
    via X-Session-Id header. This will be fully implemented in Phase 5 (heartbeat)
    and Phase 7 (encrypted payloads).
    """
    session_id = request.headers.get("X-Session-Id")
    if session_id is None:
        raise HTTPException(status_code=401, detail="Missing session ID")

    # Phase 5+: verify session exists and is valid
    # For now, allow through
    return {"session_id": session_id}


# ---------------------------------------------------------------------------
# NoSQL injection sanitization middleware
# ---------------------------------------------------------------------------

_NOSQL_DANGEROUS_CHARS = re.compile(r'[\$\.\x00]')


def sanitize_value(value: Any) -> Any:
    """Recursively sanitize a value to prevent NoSQL injection.

    Strips $ and . from field names in dicts (when used as query operators).
    For string values, rejects null bytes.
    """
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, val in value.items():
            # MongoDB operators start with $ — block keys that start with $
            if isinstance(key, str) and key.startswith("$"):
                raise ValueError(f"Unsafe query operator: {key}")
            # Block null bytes in keys
            if isinstance(key, str) and "\x00" in key:
                raise ValueError(f"Unsafe null byte in key: {key}")
            sanitized[key] = sanitize_value(val)
        return sanitized
    elif isinstance(value, list):
        return [sanitize_value(item) for item in value]
    elif isinstance(value, str):
        if "\x00" in value:
            raise ValueError("Unsafe null byte in value")
        return value
    return value


class NoSQLInjectionMiddleware(BaseHTTPMiddleware):
    """Middleware that sanitizes request bodies against NoSQL injection."""

    async def dispatch(self, request: Request, call_next):
        # Sanitize path parameters
        for key, value in request.path_params.items():
            if isinstance(value, str) and _NOSQL_DANGEROUS_CHARS.search(value):
                raise HTTPException(status_code=400, detail="Invalid path parameter")

        # Sanitize query parameters
        for key, values in request.query_params.multi_items():
            if _NOSQL_DANGEROUS_CHARS.search(key):
                raise HTTPException(status_code=400, detail="Invalid query parameter")
            if _NOSQL_DANGEROUS_CHARS.search(values):
                raise HTTPException(status_code=400, detail="Invalid query value")

        # Sanitize JSON body
        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    body = await request.json()
                    sanitize_value(body)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc))

        response = await call_next(request)
        return response


# ---------------------------------------------------------------------------
# IP-based rate limiting (simple in-memory for Free Tier)
# ---------------------------------------------------------------------------

from collections import defaultdict
from datetime import datetime, timezone

_rate_limit_store: dict[str, list[float]] = defaultdict(list)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware.

    Not suitable for multi-process deployments. For production at scale,
    replace with Redis-backed rate limiting.
    """

    async def dispatch(self, request: Request, call_next):
        # Only rate-limit the validation endpoint
        if request.url.path.rstrip("/") != "/licenses/validate":
            return await call_next(request)

        from app.core.config import settings

        client_ip = request.client.host if request.client else "unknown"
        now = datetime.now(tz=timezone.utc).timestamp()
        window = settings.validation_rate_window_seconds
        limit = settings.validation_rate_limit

        # Clean old entries
        _rate_limit_store[client_ip] = [
            ts for ts in _rate_limit_store.get(client_ip, []) if now - ts < window
        ]

        if len(_rate_limit_store[client_ip]) >= limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        _rate_limit_store[client_ip].append(now)
        return await call_next(request)
