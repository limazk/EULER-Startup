"""Shared HTTP security controls for the public EULER preview.

These controls protect the demonstration endpoint from accidental and low-cost
abuse. The in-process rate limiter is deliberately a second line of defense:
on serverless platforms it is per warm instance, so edge/WAF rate limiting
should also be enabled in production.
"""
from __future__ import annotations

from collections import defaultdict, deque
from email.message import Message
import math
import os
import threading
import time
from urllib.parse import urlsplit

MAX_BODY_BYTES = 3_000_000


def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


RATE_LIMIT_MAX = _bounded_env_int("EULER_RATE_LIMIT_MAX", 20, 1, 1000)
RATE_LIMIT_WINDOW_SECONDS = _bounded_env_int(
    "EULER_RATE_LIMIT_WINDOW_SECONDS", 60, 10, 3600
)

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "worker-src 'self' blob:; "
        "media-src 'self'; "
        "manifest-src 'self'; "
        "upgrade-insecure-requests"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=(), serial=()"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-Permitted-Cross-Domain-Policies": "none",
}


class SlidingWindowRateLimiter:
    """Small thread-safe limiter for local and warm serverless instances."""

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> tuple[bool, int]:
        now = time.monotonic() if now is None else now
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                retry_after = max(1, math.ceil(bucket[0] + self.window_seconds - now))
                return False, retry_after
            bucket.append(now)

            if len(self._hits) > 10_000:
                stale = [k for k, q in self._hits.items() if not q or q[-1] <= cutoff]
                for stale_key in stale[:5_000]:
                    self._hits.pop(stale_key, None)
            return True, 0


RATE_LIMITER = SlidingWindowRateLimiter(RATE_LIMIT_MAX, RATE_LIMIT_WINDOW_SECONDS)


def media_type(headers) -> str:
    """Return a normalized Content-Type media type without trusting parameters."""
    raw = headers.get("Content-Type", "")
    msg = Message()
    msg["content-type"] = raw
    return msg.get_content_type().lower() if raw else ""


def same_origin(headers) -> bool:
    """Reject browser cross-site submissions while allowing non-browser clients."""
    fetch_site = (headers.get("Sec-Fetch-Site") or "").lower()
    if fetch_site == "cross-site":
        return False

    origin = headers.get("Origin")
    if not origin:
        return True
    try:
        origin_parts = urlsplit(origin)
    except ValueError:
        return False
    host = (headers.get("Host") or "").lower()
    return bool(
        host
        and origin_parts.scheme in {"http", "https"}
        and origin_parts.netloc.lower() == host
    )


def content_length(headers) -> int:
    """Validate body framing and return a safe Content-Length."""
    if headers.get("Transfer-Encoding"):
        raise ValueError("transfer-encoding")
    encoding = (headers.get("Content-Encoding") or "identity").lower().strip()
    if encoding not in {"", "identity"}:
        raise ValueError("content-encoding")
    raw = headers.get("Content-Length")
    if raw is None:
        raise ValueError("content-length")
    try:
        length = int(raw)
    except (TypeError, ValueError):
        raise ValueError("content-length") from None
    if not 0 < length <= MAX_BODY_BYTES:
        raise OverflowError("content-length")
    return length


def client_key(headers, fallback: str) -> str:
    """Use Vercel's forwarded address only on Vercel; otherwise trust the socket."""
    if os.getenv("VERCEL") == "1":
        forwarded = headers.get("X-Forwarded-For")
        if forwarded:
            candidate = forwarded.split(",", 1)[0].strip()
            if candidate:
                return candidate[:128]
    return (fallback or "unknown")[:128]
