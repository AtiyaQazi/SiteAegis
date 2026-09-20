from fastapi import APIRouter

from app.core.config import settings
from app.core.redis import redis_manager
from app.schemas.common import HealthResponse


router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("")
def health_check():
    redis_status = (
        "connected"
        if redis_manager.ping()
        else "disconnected"
    )

    response = HealthResponse(
        status="healthy",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
    )

    return {
        **response.model_dump(),
        "services": {
            "redis": redis_status,
        },
    }