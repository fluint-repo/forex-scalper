"""API key authentication dependency."""

from fastapi import Depends, HTTPException, Query, Request, status

from config.settings import API_KEY


def require_api_key(
    request: Request,
    api_key: str | None = Query(None, alias="api_key"),
) -> None:
    """FastAPI dependency: checks X-API-Key header or api_key query param.

    If API_KEY setting is empty, auth is disabled (dev mode).
    """
    if not API_KEY:
        return  # Auth disabled

    key = request.headers.get("X-API-Key") or api_key

    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
        )

    if key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
