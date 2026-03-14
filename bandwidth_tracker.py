"""
Bandwidth tracking middleware for monitoring outbound usage.
Logs bandwidth usage by endpoint and helps identify optimization opportunities.
"""
import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("bandwidth")

class BandwidthTrackerMiddleware(BaseHTTPMiddleware):
    """
    Tracks outbound bandwidth usage for all API responses.
    Logs when response size exceeds thresholds.
    """

    def __init__(self, app, warn_mb=1, alert_mb=10):
        super().__init__(app)
        self.warn_mb = warn_mb
        self.alert_mb = alert_mb

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate bandwidth
        process_time = time.time() - start_time
        response_size = len(response.body) if hasattr(response, 'body') else 0
        response_size_kb = response_size / 1024
        response_size_mb = response_size_kb / 1024

        # Track by endpoint
        path = request.url.path
        method = request.method

        # Log large responses
        if response_size_mb >= self.alert_mb:
            logger.warning(
                f"[BANDWIDTH ALERT] {method} {path} - "
                f"Response size: {response_size_mb:.2f}MB (threshold: {self.alert_mb}MB)"
            )
        elif response_size_mb >= self.warn_mb:
            logger.info(
                f"[BANDWIDTH] {method} {path} - "
                f"Response size: {response_size_mb:.2f}MB (threshold: {self.warn_mb}MB)"
            )

        # Add bandwidth header (optional, for debugging)
        response.headers["X-Response-Size"] = f"{response_size}"

        return response


class BandwidthReportMiddleware(BaseHTTPMiddleware):
    """
    Provides a /bandwidth endpoint showing usage stats.
    """

    def __init__(self, app):
        super().__init__(app)
        self.stats = {}

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/bandwidth/stats":
            total_bytes = sum(s["bytes"] for s in self.stats.values())
            total_requests = sum(s["requests"] for s in self.stats.values())

            stats_summary = {
                "total_bytes": total_bytes,
                "total_mb": round(total_bytes / 1024 / 1024, 2),
                "total_requests": total_requests,
                "endpoints": self.stats
            }

            from fastapi.responses import JSONResponse
            return JSONResponse(stats_summary)

        # Track usage
        response = await call_next(request)
        response_size = len(response.body) if hasattr(response, 'body') else 0

        path = request.url.path
        if path not in self.stats:
            self.stats[path] = {"bytes": 0, "requests": 0}
        self.stats[path]["bytes"] += response_size
        self.stats[path]["requests"] += 1

        return response
