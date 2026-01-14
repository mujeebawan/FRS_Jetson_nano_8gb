"""API route modules"""

from fastapi import APIRouter, Request

from .stream import router as stream_router
from .persons import router as persons_router
from .alerts import router as alerts_router
from .system import router as system_router
from .cameras import router as cameras_router
from .auth import router as auth_router
from .users import router as users_router

api_router = APIRouter()


@api_router.get("/health")
async def health_check(request: Request):
    """Health check endpoint for startup and monitoring."""
    from ...models.database import Camera, get_db, SessionLocal

    stream = getattr(request.app.state, 'stream', None)
    recognizer = getattr(request.app.state, 'recognizer', None)

    # Get camera count from database
    db = SessionLocal()
    try:
        camera_count = db.query(Camera).filter(Camera.enabled == True).count()
        cameras_online = db.query(Camera).filter(Camera.is_online == True).count()
    finally:
        db.close()

    return {
        "status": "healthy",
        "cameras_enabled": camera_count,
        "cameras_online": cameras_online,
        "stream_running": stream.is_running if stream else False,
        "persons_enrolled": recognizer.person_count if recognizer else 0
    }


api_router.include_router(auth_router)  # /api/auth/*
api_router.include_router(users_router)  # /api/users/*
api_router.include_router(cameras_router, prefix="/cameras", tags=["Cameras"])
api_router.include_router(stream_router, prefix="/stream", tags=["Stream"])
api_router.include_router(persons_router, prefix="/persons", tags=["Persons"])
api_router.include_router(alerts_router, prefix="/alerts", tags=["Alerts"])
api_router.include_router(system_router, prefix="/system", tags=["System"])
