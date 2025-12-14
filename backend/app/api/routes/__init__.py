"""API route modules"""

from fastapi import APIRouter, Request

from .stream import router as stream_router
from .persons import router as persons_router
from .alerts import router as alerts_router
from .system import router as system_router
from .auth import router as auth_router
from .users import router as users_router

api_router = APIRouter()


@api_router.get("/health")
async def health_check(request: Request):
    """Health check endpoint for startup and monitoring."""
    from ...config import settings

    stream = getattr(request.app.state, 'stream', None)
    recognizer = getattr(request.app.state, 'recognizer', None)

    return {
        "status": "healthy",
        "camera_ip": settings.camera_ip,
        "stream_running": stream.is_running if stream else False,
        "persons_enrolled": recognizer.person_count if recognizer else 0
    }


# Auth routes (no prefix needed, already has /auth)
api_router.include_router(auth_router)
api_router.include_router(users_router)

# Feature routes
api_router.include_router(stream_router, prefix="/stream", tags=["Stream"])
api_router.include_router(persons_router, prefix="/persons", tags=["Persons"])
api_router.include_router(alerts_router, prefix="/alerts", tags=["Alerts"])
api_router.include_router(system_router, prefix="/system", tags=["System"])
