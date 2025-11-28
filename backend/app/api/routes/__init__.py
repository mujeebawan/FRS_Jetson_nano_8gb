"""API route modules"""

from fastapi import APIRouter

from .stream import router as stream_router
from .persons import router as persons_router
from .alerts import router as alerts_router
from .system import router as system_router

api_router = APIRouter()

api_router.include_router(stream_router, prefix="/stream", tags=["Stream"])
api_router.include_router(persons_router, prefix="/persons", tags=["Persons"])
api_router.include_router(alerts_router, prefix="/alerts", tags=["Alerts"])
api_router.include_router(system_router, prefix="/system", tags=["System"])
