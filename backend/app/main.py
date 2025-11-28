"""
Face Recognition Security System - Main Application
Optimized for Jetson Orin Nano 8GB
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .config import settings
from .api.routes import api_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Face Recognition Security System...")
    logger.info(f"Camera: {settings.camera_ip}")
    logger.info(f"Stream: {settings.process_stream} (skip={settings.frame_skip})")

    # Initialize services
    from .services.camera import CameraService
    from .services.stream import StreamManager
    from .core import FaceDetector, FaceRecognizer

    app.state.camera = CameraService()
    app.state.stream = StreamManager(frame_skip=settings.frame_skip)
    app.state.detector = FaceDetector(
        model_name=settings.recognition_model,
        min_confidence=settings.detection_confidence
    )
    app.state.recognizer = FaceRecognizer(
        embeddings_dir=settings.embeddings_dir,
        threshold=settings.recognition_threshold
    )

    # Load saved embeddings
    app.state.recognizer.load()

    # Get camera info
    info = await app.state.camera.get_device_info()
    if info:
        logger.info(f"Connected to {info.model} (FW: {info.firmware})")

    yield

    # Shutdown
    logger.info("Shutting down...")
    app.state.stream.stop()
    await app.state.camera.close()
    app.state.recognizer.save()


# Create FastAPI app
app = FastAPI(
    title="Face Recognition Security System",
    description="Real-time face detection and recognition for security monitoring",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",  # Vite default
        "http://192.168.0.245:5173",  # Vite on WiFi
        "http://192.168.1.100:5173",  # Vite on Ethernet
        "http://192.168.0.245:3000",
        "http://192.168.1.100:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(api_router, prefix="/api")

# Serve static files (for production, frontend build)
static_path = Path(__file__).parent.parent.parent / "frontend" / "dist"
if static_path.exists():
    app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "camera_ip": settings.camera_ip,
        "stream_running": app.state.stream.is_running if hasattr(app.state, 'stream') else False,
        "persons_enrolled": app.state.recognizer.person_count if hasattr(app.state, 'recognizer') else 0
    }
