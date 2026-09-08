from fastapi import APIRouter

from app.core.config import settings
from app.schemas.common import HealthResponse


router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("")
def health_check():
    return HealthResponse(
        status="healthy",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
    )