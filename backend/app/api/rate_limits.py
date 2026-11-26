"""Per-client limits on the endpoints that accept passwords."""

import math

from fastapi import HTTPException, Request, status

from app.core.config import Settings
from app.core.rate_limit import SlidingWindowLimiter


def client_address(request: Request, trusted_proxy_hops: int, client_ip_header: str = "") -> str:
    """The caller's address.

    A configured edge header wins, because it does not depend on how many proxies are in between.
    Otherwise, behind proxies, only the entries our own proxies appended to X-Forwarded-For can be
    believed, so count from the right. Anything further left was supplied by the caller.
    """
    if client_ip_header and (from_edge := request.headers.get(client_ip_header, "").strip()):
        return from_edge
    if trusted_proxy_hops > 0:
        forwarded = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",")]
        if len(forwarded) >= trusted_proxy_hops and forwarded[-trusted_proxy_hops]:
            return forwarded[-trusted_proxy_hops]
    return request.client.host if request.client else "unknown"


def limit_auth_attempts(request: Request) -> None:
    """Dependency: slows password guessing and bulk sign-ups. Each endpoint counts separately."""
    settings: Settings = request.app.state.settings
    limiter: SlidingWindowLimiter = request.app.state.auth_limiter
    address = client_address(request, settings.trusted_proxy_hops, settings.client_ip_header)
    key = f"{request.url.path}|{address}"
    wait = limiter.retry_after(key)
    if wait > 0:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many attempts. Wait a minute and try again.",
            headers={"Retry-After": str(math.ceil(wait))},
        )
