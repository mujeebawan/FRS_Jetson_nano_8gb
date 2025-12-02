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

    # Initialize database tables
    from .models.database import init_db, get_db, Person
    init_db()
    logger.info("Database tables initialized")

    # Initialize services
    from .services.camera import CameraService
    from .services.stream import StreamManager
    from .services.processor import FrameProcessor
    from .services.alerts import AlertManager
    from .core import FaceDetector, FaceRecognizer

    app.state.camera = CameraService()
    app.state.stream = StreamManager(frame_skip=settings.frame_skip)
    app.state.detector = FaceDetector(
        model_name=settings.recognition_model,
        min_confidence=settings.detection_confidence,
        use_gpu=settings.use_gpu,
        use_fp16=settings.use_fp16  # Use FP16 models for faster GPU inference
    )
    app.state.recognizer = FaceRecognizer(
        embeddings_dir=settings.embeddings_dir,
        threshold=settings.recognition_threshold,
        model_name=settings.recognition_model
    )

    # Load saved embeddings
    app.state.recognizer.load()

    # Initialize alert manager
    app.state.alert_manager = AlertManager()
    logger.info(f"AlertManager initialized (cooldown={settings.alert_cooldown_seconds}s)")

    # Create alert callback for face detection
    def alert_callback(detection, frame_data):
        """Callback when face is detected - creates alert with cooldown."""
        from .api.routes.alerts import broadcast_alert_sync
        try:
            # Get a database session
            db = next(get_db())
            try:
                # Check if person is recognized
                person = None
                similarity = None
                if detection.embedding is not None:
                    result = app.state.recognizer.identify(detection.embedding)
                    if result and result.is_match:
                        # Known person - look up in database
                        person = db.query(Person).filter(Person.name == result.person_name).first()
                        similarity = result.similarity

                # Create alert (AlertManager handles cooldown internally)
                alert = app.state.alert_manager.create_alert(
                    db=db,
                    event_type="face_detected",
                    person=person,
                    confidence=detection.confidence,
                    similarity_score=similarity,
                    frame=frame_data.frame if frame_data else None
                )

                # Broadcast to WebSocket subscribers (thread-safe sync version)
                if alert:
                    broadcast_alert_sync(alert)

            finally:
                db.close()
        except Exception as e:
            logger.error(f"Alert callback error: {e}")

    # Connect frame processor object to stream for face detection
    # Pass the object (not function) so stream can call draw_overlay() for non-detection frames
    app.state.processor = FrameProcessor(
        detector=app.state.detector,
        recognizer=app.state.recognizer,
        alert_callback=alert_callback
    )
    app.state.stream.set_processor(app.state.processor)
    logger.info("Frame processor connected to stream with alert callback")

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
    lifespan=lifespan,
    redirect_slashes=True  # Allow both /persons and /persons/
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
