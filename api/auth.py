import secrets

from fastapi import Header, HTTPException, status

from api.config import get_settings


async def check_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Optional API key authentication.

    If API_KEY is configured in settings, all requests must include
    a matching X-Api-Key header. If API_KEY is not set, all requests
    are allowed (localhost-friendly).
    """
    settings = get_settings()
    if not settings.api_key:
        return

    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
