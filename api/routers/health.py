from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from api.config import get_settings

settings = get_settings()
router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["healthy", "unhealthy"]
    app: str
    version: str


@router.get("/health", response_model=HealthResponse, include_in_schema=False)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        app=settings.app_name,
        version=settings.app_version,
    )
