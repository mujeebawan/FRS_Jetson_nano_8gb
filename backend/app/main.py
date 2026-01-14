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


def seed_initial_cameras(db):
    """Seed initial cameras if no cameras exist."""
    from .models.database import Camera

    # Check if any cameras exist
    camera_count = db.query(Camera).count()
    if camera_count == 0:
        # Create Camera 1
        camera1 = Camera(
            name="Camera 1",
            ip_address="192.168.1.70",
            port=554,
            username="admin",
            password="Admin@123",
            stream_quality="sub",  # 720p 25fps
            enabled=True,
            detection_enabled=True,
            location="Main Entrance",
            notes="Hikvision DS-2CD7A47EWD-XZS"
        )
        # Create Camera 2
        camera2 = Camera(
            name="Camera 2",
            ip_address="192.168.1.72",
            port=554,
            username="admin",
            password="Admin@123",
            stream_quality="sub",  # 720p 25fps
            enabled=True,
            detection_enabled=True,
            location="Back Entrance",
            notes="Hikvision Camera 2"
        )
        db.add(camera1)
        db.add(camera2)
        db.commit()
        logger.info(f"Seeded cameras: {camera1.name}, {camera2.name}")
        return 2
    return camera_count


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Face Recognition Security System - Base System V2...")
    logger.info(f"Model: {settings.recognition_model}, TensorRT: {settings.use_tensorrt}")
    logger.info(f"Frame skip: {settings.frame_skip}")

    # Initialize database tables
    from .models.database import init_db, get_db, Person, Camera, SessionLocal
    init_db()
    logger.info("Database tables initialized")

    # Seed initial camera if needed and get primary camera for streaming
    db = SessionLocal()
    primary_camera = None
    try:
        camera_count = seed_initial_cameras(db)
        enabled_cameras = db.query(Camera).filter(Camera.enabled == True).all()
        logger.info(f"Cameras configured: {camera_count} total, {len(enabled_cameras)} enabled")
        for cam in enabled_cameras:
            logger.info(f"  - {cam.name}: {cam.ip_address} ({cam.stream_quality})")

        # Get first enabled camera as primary for streaming
        if enabled_cameras:
            primary_camera = enabled_cameras[0]
            logger.info(f"Primary camera for streaming: {primary_camera.name}")
    finally:
        db.close()

    # Initialize services
    from .services.camera import CameraService
    from .services.alerts import AlertManager
    from .core.recognizer import FaceRecognizer

    # Create camera services for all enabled cameras (for PTZ control)
    app.state.cameras = {}
    for cam in enabled_cameras:
        app.state.cameras[cam.id] = CameraService(
            ip=cam.ip_address,
            username=cam.username,
            password=cam.password
        )
    # Primary camera (backward compatibility)
    app.state.camera = app.state.cameras.get(enabled_cameras[0].id) if enabled_cameras else CameraService()

    # Initialize recognizer first (needed by DeepStream)
    app.state.recognizer = FaceRecognizer(
        embeddings_dir=settings.embeddings_dir,
        threshold=settings.recognition_threshold,
        use_gpu=settings.faiss_use_gpu,
        model_name=settings.recognition_model
    )
    app.state.recognizer.load()
    logger.info(f"Recognizer loaded {app.state.recognizer.count} persons")

    # Initialize alert manager
    app.state.alert_manager = AlertManager()
    logger.info(f"AlertManager initialized (cooldown={settings.alert_cooldown_seconds}s)")

    # Initialize video recorder for alert clips (if enabled)
    from .services.video_recorder import VideoRecorder
    if settings.video_recording_enabled:
        clip_duration = settings.video_clip_duration
        app.state.video_recorder = VideoRecorder(
            pre_alert_seconds=float(clip_duration),
            post_alert_seconds=float(clip_duration),
            fps=15,  # 15 FPS for clips (saves space)
            clips_dir=settings.clips_dir
        )
        logger.info(f"VideoRecorder initialized ({clip_duration}s pre + {clip_duration}s post @ 15fps)")
    else:
        app.state.video_recorder = None
        logger.info("VideoRecorder disabled")

    # Create alert callback for face detection
    def alert_callback(detection, frame_data):
        """Callback when face is detected - creates alert with cooldown."""
        from .api.routes.alerts import broadcast_alert_sync
        try:
            db = next(get_db())
            try:
                person = None
                similarity = None
                if detection.embedding is not None:
                    result = app.state.recognizer.identify(detection.embedding)
                    if result and result.is_match:
                        person = db.query(Person).filter(Person.name == result.person_name).first()
                        similarity = result.similarity
                        logger.info(f"Face recognized: {result.person_name} (sim={result.similarity:.2f})")

                # Extract single camera frame and adjust bbox coordinates
                camera_frame = None
                adjusted_bbox = detection.bbox if detection else None
                camera_id = getattr(detection, 'camera_id', 0)
                camera_name = None

                if frame_data and frame_data.frame is not None and hasattr(app.state.stream, '_cameras'):
                    stream = app.state.stream
                    num_cameras = len(stream._cameras)

                    if num_cameras > 0:
                        # Get camera info
                        camera_index = camera_id  # camera_id in detection is actually the index
                        if camera_index < len(stream._cameras):
                            cam = stream._cameras[camera_index]
                            camera_id = cam.id
                            camera_name = cam.name

                        # Extract single camera frame from tiled view
                        tiler_cols = min(num_cameras, 2)
                        tile_width = 960
                        tile_height = 540

                        col = camera_index % tiler_cols
                        row = camera_index // tiler_cols

                        x1 = col * tile_width
                        y1 = row * tile_height
                        x2 = x1 + tile_width
                        y2 = y1 + tile_height

                        full_frame = frame_data.frame
                        if y2 <= full_frame.shape[0] and x2 <= full_frame.shape[1]:
                            camera_frame = full_frame[y1:y2, x1:x2].copy()

                            # Adjust bbox coordinates relative to single camera frame
                            if detection and detection.bbox:
                                bx, by, bw, bh = detection.bbox
                                adjusted_bbox = (bx - x1, by - y1, bw, bh)
                        else:
                            camera_frame = full_frame  # Fallback to full frame
                    else:
                        camera_frame = frame_data.frame
                else:
                    camera_frame = frame_data.frame if frame_data else None

                alert = app.state.alert_manager.create_alert(
                    db=db,
                    event_type="face_detected",
                    person=person,
                    confidence=detection.confidence,
                    similarity_score=similarity,
                    frame=camera_frame,
                    bbox=adjusted_bbox,
                    camera_id=camera_id,
                    camera_name=camera_name
                )

                if alert:
                    logger.info(f"Alert created: {alert.id} - {alert.person_name}")
                    broadcast_alert_sync(alert)

                    if app.state.video_recorder:
                        try:
                            app.state.video_recorder.trigger_recording(
                                alert_id=alert.id,
                                bbox=detection.bbox if detection else None
                            )
                        except Exception as ve:
                            logger.error(f"Video recording trigger failed: {ve}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Alert callback error: {e}", exc_info=True)

    # Try DeepStream first, fall back to OpenCV stream
    use_deepstream = True
    try:
        from .services.deepstream_stream import DeepStreamManager, PYDS_AVAILABLE
        if not PYDS_AVAILABLE:
            raise ImportError("pyds not available")

        # Pass all enabled cameras for multi-camera pipeline
        app.state.stream = DeepStreamManager(
            cameras=enabled_cameras,  # All enabled cameras
            frame_skip=settings.frame_skip,
            recognizer=app.state.recognizer,
            alert_callback=alert_callback
        )

        # Initialize detector for enrollment (uses InsightFace ONNX, separate from DeepStream TRT)
        from .core import FaceDetector
        app.state.detector = FaceDetector(
            model_name=settings.recognition_model,
            min_confidence=settings.detection_confidence,
            use_gpu=settings.use_gpu,
            use_fp16=settings.use_fp16
        )
        app.state.processor = None  # Not needed with DeepStream
        logger.info(f"Using DeepStream pipeline with {len(enabled_cameras)} cameras")
        logger.info("Enrollment detector initialized (InsightFace ONNX)")

    except Exception as e:
        logger.warning(f"DeepStream not available ({e}), falling back to OpenCV")
        use_deepstream = False

        from .services.stream import StreamManager
        from .services.processor import FrameProcessor
        from .core import FaceDetector

        app.state.detector = FaceDetector(
            model_name=settings.recognition_model,
            min_confidence=settings.detection_confidence,
            use_gpu=settings.use_gpu,
            use_fp16=settings.use_fp16
        )

        app.state.stream = StreamManager(
            frame_skip=settings.frame_skip,
            camera=primary_camera
        )

        app.state.processor = FrameProcessor(
            detector=app.state.detector,
            recognizer=app.state.recognizer,
            alert_callback=alert_callback
        )
        app.state.stream.set_processor(app.state.processor)
        logger.info("Using OpenCV stream with ONNX detection")

    # Connect video recorder to stream (if available)
    if hasattr(app.state.stream, 'set_video_recorder') and app.state.video_recorder:
        app.state.stream.set_video_recorder(app.state.video_recorder)

    # Get camera info
    info = await app.state.camera.get_device_info()
    if info:
        logger.info(f"Connected to {info.model} (FW: {info.firmware})")

    # Auto-start stream on startup
    if app.state.stream.start():
        logger.info("Camera stream auto-started")
    else:
        logger.warning("Failed to auto-start camera stream")

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
