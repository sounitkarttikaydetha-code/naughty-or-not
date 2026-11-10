"""
Middleware for Clearance Check Canary API:
- Request size limiter (10MB limit)
- In-memory rate limiter
- Global Canary response headers (engine version, list dates, evaluation notice)
"""
import time
from collections import defaultdict
from typing import Dict, List, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
RATE_LIMIT_REQUESTS = 300              # 300 req / minute
RATE_LIMIT_WINDOW = 60.0               # 60 seconds

CANARY_NOTICE = "Canary build — for evaluation only. Not for screening decisions."
CANARY_HEADER_NOTICE = "Canary build - for evaluation only. Not for screening decisions."
ENGINE_VERSION = "2.0.1-canary.1"


class CanaryResponseHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces standard security and Canary audit headers on every response."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Engine-Version"] = ENGINE_VERSION
        response.headers["X-Canary-Notice"] = CANARY_HEADER_NOTICE
        response.headers["X-List-Dates"] = "US OFAC: 2026-10-24, US CSL: 2026-10-24, UK CSL: 2026-10-24, EU CSL: 2026-10-24, UN CSL: 2026-10-24"
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects requests exceeding the maximum allowed body size."""

    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl:
            try:
                length = int(cl)
                if length > MAX_CONTENT_LENGTH:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "type": "https://clearancecheck.canary/errors/payload-too-large",
                            "title": "Payload Too Large",
                            "status": 413,
                            "detail": f"Request body length {length} bytes exceeds 10MB limit.",
                            "instance": request.url.path,
                            "code": "REQUEST_TOO_LARGE",
                        },
                        media_type="application/problem+json",
                    )
            except ValueError:
                pass
        return await call_next(request)


class InMemoryRateLimiterMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter per client IP address."""

    def __init__(self, app, max_requests: int = RATE_LIMIT_REQUESTS, window: float = RATE_LIMIT_WINDOW):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window
        self.client_hits: Dict[str, List[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Exempt health & readiness probes from rate limiting
        if request.url.path in ("/health", "/ready", "/metrics"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()

        # Clean expired timestamps
        hits = [t for t in self.client_hits[client_ip] if (now - t) < self.window]
        if len(hits) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "type": "https://clearancecheck.canary/errors/rate-limit-exceeded",
                    "title": "Too Many Requests",
                    "status": 429,
                    "detail": f"Rate limit exceeded: maximum {self.max_requests} requests per {int(self.window)} seconds.",
                    "instance": request.url.path,
                    "code": "RATE_LIMIT_EXCEEDED",
                },
                media_type="application/problem+json",
                headers={"Retry-After": "30"},
            )

        hits.append(now)
        self.client_hits[client_ip] = hits

        return await call_next(request)
