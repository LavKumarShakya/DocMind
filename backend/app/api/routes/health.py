"""Health-check endpoints used by docker-compose and developers."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(
    response: Response,
    db: Session = Depends(get_db),
) -> HealthResponse:
    """Report overall API health and database connectivity."""
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        database="ok" if db_ok else "unavailable",
    )