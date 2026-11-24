from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import get_engine

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
def liveness() -> dict[str, str]:
    """Reports that the process is running. Does not touch the database."""
    settings = get_settings()
    return {"status": "ok", "version": settings.app_version, "environment": settings.environment}


@router.get("/health/ready", summary="Readiness probe")
def readiness() -> JSONResponse:
    """Reports whether the service can serve traffic, which requires a working database connection."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "database": "unreachable"},
        )
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ready", "database": "ok"})
