"""
API Security Middleware

Provides middleware for validating and sanitizing API request inputs.
"""

import hashlib
import hmac
import json
import logging
import time
from typing import Callable, Dict
from urllib.parse import parse_qs

from fastapi import Request, status
from fastapi.responses import JSONResponse

from config import settings

log = logging.getLogger(__name__)


class RateLimitMiddleware:
    """
    Rate limiting middleware to prevent spam and abuse.

    Different limits based on user role:
    - Overlord (main bot owner): Very high limit
    - Clone owners: Higher limit than regular users
    - Regular users: Standard limit
    """

    def __init__(self):
        # Simple in-memory rate limiter
        # In production, use Redis for distributed rate limiting
        self.requests: Dict[str, Dict[str, list]] = {}
        self._last_pruned: float = 0.0
        self.rate_limits = {
            "default": {"requests": 100, "window": 60},  # 100 req/min for regular users
            "clone_owner": {"requests": 200, "window": 60},  # 200 req/min for clone owners
            "overlord": {"requests": 5000, "window": 60},  # Overlord has very high limit
            "strict": {"requests": 30, "window": 60},  # 30 req/min
            "upload": {"requests": 10, "window": 60},  # 10 req/min
        }
        # Paths to skip rate limiting entirely (static assets, health checks)
        self.skip_paths = [
            "/miniapp/",
            "/static/",
            "/health",
            "/api/i18n",  # Translation endpoint - lightweight
        ]

    def _should_skip_rate_limit(self, path: str) -> bool:
        """Check if path should skip rate limiting."""
        for skip_path in self.skip_paths:
            if path.startswith(skip_path):
                return True
        # Also skip static file extensions
        static_extensions = (
            '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
            '.woff', '.woff2', '.ttf', '.eot'
        )
        if path.lower().endswith(static_extensions):
            return True
        return False

    async def __call__(self, request: Request, call_next: Callable):
        """Process request and apply rate limiting."""
        client_ip = self._get_client_ip(request)
        path = request.url.path

        # Skip rate limiting for static assets and health endpoints
        if self._should_skip_rate_limit(path):
            return await call_next(request)

        # Determine rate limit based on path and user role
        limit_type = "default"
        if "/upload" in path or "/restore" in path:
            limit_type = "upload"
        elif "/clone" in path or "/token" in path:
            limit_type = "strict"

        # Detect user role from auth headers for role-based rate limiting
        user_role = self._detect_user_role_from_request(request)
        if user_role == "overlord":
            limit_type = "overlord"
        elif user_role == "clone_owner":
            limit_type = "clone_owner"

        limit_config = self.rate_limits[limit_type]
        current_time = time.time()
        window_start = current_time - limit_config["window"]

        # Periodically prune stale IPs (every 2 minutes)
        if current_time - self._last_pruned > 120:
            self._last_pruned = current_time
            max_window = max(lc["window"] for lc in self.rate_limits.values())
            cutoff = current_time - 2 * max_window
            stale_ips = []
            for ip, buckets in self.requests.items():
                # Check if all buckets are stale
                all_stale = True
                for bucket_type, timestamps in buckets.items():
                    if timestamps and timestamps[-1] >= cutoff:
                        all_stale = False
                        break
                if all_stale:
                    stale_ips.append(ip)
            for ip in stale_ips:
                del self.requests[ip]

        # Initialize rate limit bucket for this IP if needed
        if client_ip not in self.requests:
            self.requests[client_ip] = {}

        # Clean old requests for this limit type
        if limit_type in self.requests[client_ip]:
            self.requests[client_ip][limit_type] = [
                req_time for req_time in self.requests[client_ip][limit_type] if req_time > window_start
            ]
        else:
            self.requests[client_ip][limit_type] = []

        # Check rate limit
        if len(self.requests[client_ip][limit_type]) >= limit_config["requests"]:
            log.warning(f"[RATE_LIMIT] IP {client_ip} exceeded rate limit for {path} (type={limit_type})")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Too many requests. Please slow down.",
                    "retry_after": limit_config["window"],
                },
            )

        # Record request
        self.requests[client_ip][limit_type].append(current_time)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining = limit_config["requests"] - len(self.requests[client_ip][limit_type])
        response.headers["X-RateLimit-Limit"] = str(limit_config["requests"])
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Window"] = str(limit_config["window"])

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        # Check forwarded headers first
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to client
        if request.client:
            return request.client.host

        return "unknown"

    def _detect_user_role_from_request(self, request: Request) -> str:
        """
        Detect user role from auth headers to apply appropriate rate limits.
        Returns: 'overlord', 'clone_owner', or 'default'
        """
        if settings.SKIP_AUTH:
            return "overlord" if settings.OWNER_ID else "default"

        # Extract initData from request
        init_data = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("tma "):
            init_data = auth_header[4:].strip()
        else:
            init_data = (
                request.headers.get("X-Telegram-Init-Data")
                or request.headers.get("x-init-data")
                or request.query_params.get("token")
            )

        if not init_data:
            return "default"

        try:
            vals = parse_qs(init_data)
            if "hash" not in vals:
                return "default"

            user_data = json.loads(vals.get("user", ["{}"])[0])
            user_id = user_data.get("id")

            if not user_id:
                return "default"

            # Check if this is the overlord
            if user_id == settings.OWNER_ID:
                return "overlord"

            # Check if this user owns a clone bot by validating against clone tokens
            # This is a lightweight check - just see if the hash validates with any clone token
            try:
                from bot.registry import get_all

                received_hash = vals["hash"][0]
                check_vals = {k: v for k, v in vals.items() if k != "hash"}
                data_check_string = "\n".join(f"{k}={v[0]}" for k, v in sorted(check_vals.items()))

                registered_bots = get_all()
                for bot_id, bot_app in registered_bots.items():
                    try:
                        token = bot_app.bot.token
                        if token == settings.PRIMARY_BOT_TOKEN:
                            continue  # Skip primary token (already checked for overlord)

                        secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
                        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

                        if hmac.compare_digest(calculated_hash, received_hash):
                            # Valid clone token - check if user owns this clone
                            # For performance, we assume clone owner if token validates
                            # Full ownership check happens in auth.py
                            return "clone_owner"
                    except Exception:
                        continue
            except Exception:
                pass

            return "default"

        except Exception:
            return "default"


class InputValidationMiddleware:
    """
    Middleware for validating and sanitizing request inputs.
    """

    def __init__(self):
        # Paths to skip validation (bodies without user input)
        self.skip_paths = {
            "/api/me",
            "/api/groups/",
            "/api/bots",
            "/api/analytics",
            "/health",
            "/webhook",  # Telegram webhook payloads are handled by PTB
        }

    async def __call__(self, request: Request, call_next: Callable):
        """Process request and validate inputs."""
        path = request.url.path

        # Skip GET requests (they only have query params, handled by FastAPI)
        if request.method == "GET":
            return await call_next(request)

        # Skip certain paths
        if any(path.startswith(skip) for skip in self.skip_paths):
            return await call_next(request)

        # Only process JSON requests
        content_type = request.headers.get("content-type", "")
        if "application/json" not in content_type:
            return await call_next(request)

        try:
            # Read and validate body
            body = await request.json()

            # Validate JSON body
            if body and isinstance(body, dict):
                validation_result = self._validate_request_body(body, path)

                if not validation_result["valid"]:
                    log.warning(
                        f"[INPUT_VALIDATION] Rejected request to {path}: {validation_result['error']}"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "detail": f"Invalid input: {validation_result['error']}",
                            "code": "INVALID_INPUT",
                        },
                    )

                # Note: Sanitization is intentionally skipped here.
                # FastAPI re-parses the raw body via Pydantic models, so storing
                # a sanitized copy in request.state would be dead code.  The
                # validation above already rejects dangerous patterns.

        except Exception as e:
            # If validation fails, log and continue (let handler deal with it)
            log.error(f"[INPUT_VALIDATION] Error validating request: {e}")

        return await call_next(request)

    def _validate_request_body(self, body: dict, path: str) -> dict:
        """
        Validate request body for dangerous patterns.

        Returns:
            dict: {"valid": bool, "error": str}
        """
        from bot.utils.input_sanitizer import (
            detect_command_injection,
            detect_spam,
            detect_sql_injection,
            detect_xss,
        )

        # Check all string values in body
        def check_value(value, path_prefix=""):
            if isinstance(value, str):
                # Check for SQL injection
                is_sql, sql_matches = detect_sql_injection(value)
                if is_sql:
                    return False, f"SQL injection detected in {path_prefix}"

                # Check for XSS
                is_xss, xss_matches = detect_xss(value)
                if is_xss:
                    return False, f"XSS detected in {path_prefix}"

                # Check for command injection
                is_cmd, cmd_matches = detect_command_injection(value)
                if is_cmd:
                    return False, f"Command injection detected in {path_prefix}"

                # Check for spam
                is_spam, spam_reason = detect_spam(value)
                if is_spam:
                    return False, f"Spam detected in {path_prefix}: {spam_reason}"

            elif isinstance(value, dict):
                for key, val in value.items():
                    result, error = check_value(val, f"{path_prefix}.{key}" if path_prefix else key)
                    if not result:
                        return result, error

            elif isinstance(value, list):
                for i, item in enumerate(value):
                    result, error = check_value(item, f"{path_prefix}[{i}]")
                    if not result:
                        return result, error

            return True, ""

        valid, error = check_value(body, "body")
        return {"valid": valid, "error": error}

    def _sanitize_request_body(self, body: dict) -> dict:
        """
        Sanitize request body by removing dangerous patterns.

        Returns:
            dict: Sanitized body
        """
        from bot.utils.input_sanitizer import sanitize_text

        def sanitize_value(value):
            if isinstance(value, str):
                return sanitize_text(value)
            elif isinstance(value, dict):
                return {key: sanitize_value(val) for key, val in value.items()}
            elif isinstance(value, list):
                return [sanitize_value(item) for item in value]
            else:
                return value

        return sanitize_value(body)


class SecurityHeadersMiddleware:
    """
    Add security headers to all responses.
    """

    async def __call__(self, request: Request, call_next: Callable):
        """Process request and add security headers."""
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://telegram.org https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; "
            "connect-src 'self' https:; frame-ancestors 'self' https://web.telegram.org"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        return response


def log_request_response(request: Request, response):
    """Log request and response for security auditing."""
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path
    status_code = response.status_code

    # Only log errors and suspicious requests
    if status_code >= 400:
        log.warning(f"[SECURITY_LOG] {client_ip} {method} {path} -> {status_code}")
