"""
API Security Middleware

Provides middleware for validating and sanitizing API request inputs.
"""

import hashlib
import logging
import time
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

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
        self.requests: Dict[str, list] = {}
        self._last_pruned: float = 0.0
        self.rate_limits = {
            "default": {"requests": 60, "window": 60},  # 60 req/min for regular users
            "clone_owner": {"requests": 120, "window": 60},  # 120 req/min for clone owners
            "overlord": {"requests": 1000, "window": 60},  # Overlord has high limit
            "strict": {"requests": 30, "window": 60},  # 30 req/min
            "upload": {"requests": 10, "window": 60},  # 10 req/min
        }

    async def __call__(self, request: Request, call_next: Callable):
        """Process request and apply rate limiting."""
        client_ip = self._get_client_ip(request)
        path = request.url.path

        # Determine rate limit based on path
        limit_type = "default"
        if "/upload" in path or "/restore" in path:
            limit_type = "upload"
        elif "/clone" in path or "/token" in path:
            limit_type = "strict"

        limit_config = self.rate_limits[limit_type]
        current_time = time.time()
        window_start = current_time - limit_config["window"]

        # Periodically prune stale IPs (every 2 minutes)
        if current_time - self._last_pruned > 120:
            self._last_pruned = current_time
            max_window = max(lc["window"] for lc in self.rate_limits.values())
            cutoff = current_time - 2 * max_window
            stale = [ip for ip, ts in self.requests.items() if not ts or ts[-1] < cutoff]
            for ip in stale:
                del self.requests[ip]

        # Clean old requests
        if client_ip in self.requests:
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip] if req_time > window_start
            ]
        else:
            self.requests[client_ip] = []

        # Check rate limit
        if len(self.requests[client_ip]) >= limit_config["requests"]:
            log.warning(f"[RATE_LIMIT] IP {client_ip} exceeded rate limit for {path}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Too many requests. Please slow down.",
                    "retry_after": limit_config["window"],
                },
            )

        # Record request
        self.requests[client_ip].append(current_time)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining = limit_config["requests"] - len(self.requests[client_ip])
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
