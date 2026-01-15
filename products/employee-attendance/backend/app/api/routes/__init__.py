"""API route modules for Employee Attendance System"""

from fastapi import APIRouter, Request

from .stream import router as stream_router
from .employees import router as employees_router
from .attendance import router as attendance_router
from .departments import router as departments_router
from .dashboard import router as dashboard_router
from .system import router as system_router
from .cameras import router as cameras_router
from .auth import router as auth_router
from .users import router as users_router

api_router = APIRouter()


@api_router.get("/health")
async def health_check(request: Request):
    """Health check endpoint for startup and monitoring."""
    from ...models.database import Camera, Employee, get_db, SessionLocal

    stream = getattr(request.app.state, 'stream', None)
    recognizer = getattr(request.app.state, 'recognizer', None)

    db = SessionLocal()
    try:
        camera_count = db.query(Camera).filter(Camera.enabled == True).count()
        cameras_online = db.query(Camera).filter(Camera.is_online == True).count()
        employee_count = db.query(Employee).filter(Employee.is_active == True).count()
    finally:
        db.close()

    return {
        "status": "healthy",
        "cameras_enabled": camera_count,
        "cameras_online": cameras_online,
        "stream_running": stream.is_running if stream else False,
        "employees_enrolled": employee_count,
        "faces_enrolled": recognizer.person_count if recognizer else 0
    }


api_router.include_router(auth_router)  # /api/auth/*
api_router.include_router(users_router)  # /api/users/*
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(employees_router, prefix="/employees", tags=["Employees"])
api_router.include_router(attendance_router, prefix="/attendance", tags=["Attendance"])
api_router.include_router(departments_router, prefix="/departments", tags=["Departments"])
api_router.include_router(cameras_router, prefix="/cameras", tags=["Cameras"])
api_router.include_router(stream_router, prefix="/stream", tags=["Stream"])
api_router.include_router(system_router, prefix="/system", tags=["System"])
