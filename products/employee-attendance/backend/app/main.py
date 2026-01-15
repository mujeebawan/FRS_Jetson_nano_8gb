"""
Employee Attendance System - Main Application
Face Recognition based attendance tracking with first-in/last-out logic.
Optimized for Jetson Orin Nano 8GB
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import cv2
import os

from .config import settings
from .api.routes import api_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Track last attendance action per employee (in-memory cooldown)
_attendance_cooldown = {}


def seed_initial_cameras(db):
    """Seed initial cameras if no cameras exist."""
    from .models.database import Camera

    camera_count = db.query(Camera).count()
    if camera_count == 0:
        camera1 = Camera(
            name="Entrance Camera",
            ip_address="192.168.1.70",
            port=554,
            username="admin",
            password="Admin@123",
            stream_quality="sub",
            enabled=True,
            detection_enabled=True,
            location="Main Entrance",
            notes="Primary attendance camera"
        )
        camera2 = Camera(
            name="Exit Camera",
            ip_address="192.168.1.72",
            port=554,
            username="admin",
            password="Admin@123",
            stream_quality="sub",
            enabled=True,
            detection_enabled=True,
            location="Back Exit",
            notes="Secondary attendance camera"
        )
        db.add(camera1)
        db.add(camera2)
        db.commit()
        logger.info(f"Seeded cameras: {camera1.name}, {camera2.name}")
        return 2
    return camera_count


def calculate_attendance_status(check_in_time: datetime, shift_start, late_threshold: int = 15):
    """
    Calculate attendance status based on check-in time.
    Returns (status, late_minutes)
    """
    if not check_in_time or not shift_start:
        return "present", 0

    shift_start_dt = datetime.combine(check_in_time.date(), shift_start)
    late_threshold_dt = shift_start_dt + timedelta(minutes=late_threshold)

    if check_in_time <= shift_start_dt:
        return "present", 0
    elif check_in_time <= late_threshold_dt:
        late_mins = int((check_in_time - shift_start_dt).total_seconds() / 60)
        return "present", late_mins
    else:
        late_mins = int((check_in_time - shift_start_dt).total_seconds() / 60)
        return "late", late_mins


def calculate_work_hours(check_in: datetime, check_out: datetime, standard_hours: float = 8.0):
    """
    Calculate work hours and overtime.
    Returns (work_hours, overtime_hours)
    """
    if not check_in or not check_out:
        return None, None

    duration = check_out - check_in
    work_hours = duration.total_seconds() / 3600

    overtime = max(0, work_hours - standard_hours)

    return round(work_hours, 2), round(overtime, 2)


def save_attendance_snapshot(employee_id: int, frame, bbox, action: str):
    """Save attendance snapshot image."""
    try:
        snapshots_dir = Path(settings.attendance_snapshots_dir)
        snapshots_dir.mkdir(parents=True, exist_ok=True)

        today_str = date.today().strftime("%Y-%m-%d")
        filename = f"{employee_id}_{action}_{today_str}_{datetime.now().strftime('%H%M%S')}.jpg"
        filepath = snapshots_dir / filename

        # Crop face region with padding if bbox available
        if frame is not None:
            if bbox:
                x, y, w, h = bbox
                padding = 30
                x1 = max(0, int(x) - padding)
                y1 = max(0, int(y) - padding)
                x2 = min(frame.shape[1], int(x + w) + padding)
                y2 = min(frame.shape[0], int(y + h) + padding)
                face_img = frame[y1:y2, x1:x2]
            else:
                face_img = frame

            cv2.imwrite(str(filepath), face_img)
            return str(filepath)
    except Exception as e:
        logger.error(f"Failed to save attendance snapshot: {e}")
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Employee Attendance System...")
    logger.info(f"Model: {settings.recognition_model}, TensorRT: {settings.use_tensorrt}")
    logger.info(f"Late threshold: {settings.late_threshold_minutes}m, Checkout gap: {settings.checkout_gap_hours}h")

    # Initialize database tables
    from .models.database import init_db, get_db, Employee, AttendanceLog, Camera, SessionLocal
    init_db()
    logger.info("Database tables initialized")

    # Seed admin user and departments
    from .core.seed import seed_admin_user, seed_departments
    db = SessionLocal()
    primary_camera = None
    try:
        seed_admin_user(db)
        seed_departments(db)
        seed_initial_cameras(db)

        enabled_cameras = db.query(Camera).filter(Camera.enabled == True).all()
        logger.info(f"Cameras configured: {len(enabled_cameras)} enabled")
        for cam in enabled_cameras:
            logger.info(f"  - {cam.name}: {cam.ip_address} ({cam.stream_quality})")

        if enabled_cameras:
            primary_camera = enabled_cameras[0]

        employee_count = db.query(Employee).filter(Employee.is_active == True).count()
        logger.info(f"Active employees: {employee_count}")
    finally:
        db.close()

    # Initialize services
    from .services.camera import CameraService
    from .core.recognizer import FaceRecognizer

    # Create camera services for PTZ control
    app.state.cameras = {}
    for cam in enabled_cameras:
        app.state.cameras[cam.id] = CameraService(
            ip=cam.ip_address,
            username=cam.username,
            password=cam.password
        )
    app.state.camera = app.state.cameras.get(enabled_cameras[0].id) if enabled_cameras else CameraService()

    # Initialize face recognizer
    app.state.recognizer = FaceRecognizer(
        embeddings_dir=settings.embeddings_dir,
        threshold=settings.recognition_threshold,
        use_gpu=settings.faiss_use_gpu,
        model_name=settings.recognition_model
    )
    app.state.recognizer.load()
    logger.info(f"Recognizer loaded {app.state.recognizer.count} employees")

    # Attendance callback for face detection
    def attendance_callback(detection, frame_data):
        """
        Callback when face is detected - logs attendance with first-in/last-out logic.
        - First detection of the day = check-in
        - Subsequent detection after checkout_gap_hours = check-out
        """
        from .api.routes.stream import broadcast_attendance_sync
        global _attendance_cooldown

        try:
            db = next(get_db())
            try:
                employee = None
                similarity = None

                # Identify the face
                if detection.embedding is not None:
                    result = app.state.recognizer.identify(detection.embedding)
                    if result and result.is_match:
                        employee = db.query(Employee).filter(
                            Employee.name == result.person_name,
                            Employee.is_active == True
                        ).first()
                        similarity = result.similarity
                        if employee:
                            logger.debug(f"Face recognized: {employee.name} (sim={result.similarity:.2f})")

                if not employee:
                    return  # Unknown face, skip

                now = datetime.now()
                today = date.today()
                employee_key = f"{employee.id}_{today}"

                # Check cooldown (prevent duplicate logs within cooldown period)
                if employee_key in _attendance_cooldown:
                    last_action_time = _attendance_cooldown[employee_key]
                    if (now - last_action_time).total_seconds() < settings.attendance_cooldown_seconds:
                        return  # Still in cooldown

                # Get today's attendance log
                attendance_log = db.query(AttendanceLog).filter(
                    AttendanceLog.employee_id == employee.id,
                    AttendanceLog.date == today
                ).first()

                # Extract camera info
                camera_id = getattr(detection, 'camera_id', None)
                camera_name = None
                camera_frame = frame_data.frame if frame_data else None

                if hasattr(app.state.stream, '_cameras') and camera_id is not None:
                    stream = app.state.stream
                    camera_index = camera_id
                    if camera_index < len(stream._cameras):
                        cam = stream._cameras[camera_index]
                        camera_id = cam.id
                        camera_name = cam.name

                        # Extract single camera frame from tiled view
                        if frame_data and frame_data.frame is not None:
                            num_cameras = len(stream._cameras)
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

                action_type = None
                snapshot_path = None

                if not attendance_log:
                    # First detection today = CHECK-IN
                    status, late_mins = calculate_attendance_status(
                        now, employee.shift_start, settings.late_threshold_minutes
                    )

                    # Save snapshot
                    if settings.save_attendance_snapshot and camera_frame is not None:
                        snapshot_path = save_attendance_snapshot(
                            employee.id, camera_frame,
                            detection.bbox if detection else None,
                            "checkin"
                        )

                    attendance_log = AttendanceLog(
                        employee_id=employee.id,
                        date=today,
                        check_in_time=now,
                        check_in_snapshot=snapshot_path,
                        camera_id=camera_id,
                        camera_name=camera_name,
                        status=status,
                        late_minutes=late_mins if late_mins > 0 else None
                    )
                    db.add(attendance_log)
                    db.commit()

                    action_type = "check_in"
                    logger.info(f"CHECK-IN: {employee.name} at {now.strftime('%H:%M:%S')} - {status}")

                elif attendance_log.check_in_time and not attendance_log.check_out_time:
                    # Has check-in but no check-out - check if enough time passed
                    hours_since_checkin = (now - attendance_log.check_in_time).total_seconds() / 3600

                    if hours_since_checkin >= settings.checkout_gap_hours:
                        # CHECK-OUT
                        if settings.save_attendance_snapshot and camera_frame is not None:
                            snapshot_path = save_attendance_snapshot(
                                employee.id, camera_frame,
                                detection.bbox if detection else None,
                                "checkout"
                            )

                        attendance_log.check_out_time = now
                        attendance_log.check_out_snapshot = snapshot_path

                        # Calculate work hours
                        work_hours, overtime = calculate_work_hours(
                            attendance_log.check_in_time, now, settings.standard_work_hours
                        )
                        attendance_log.work_hours = work_hours
                        attendance_log.overtime_hours = overtime

                        db.commit()

                        action_type = "check_out"
                        logger.info(f"CHECK-OUT: {employee.name} at {now.strftime('%H:%M:%S')} - {work_hours}h worked")

                # Update cooldown
                _attendance_cooldown[employee_key] = now

                # Broadcast to connected clients
                if action_type:
                    broadcast_attendance_sync({
                        "type": action_type,
                        "employee_id": employee.employee_id,
                        "name": employee.name,
                        "department": employee.department.name if employee.department else None,
                        "time": now.strftime("%H:%M:%S"),
                        "timestamp": now.isoformat(),
                        "status": attendance_log.status if action_type == "check_in" else None,
                        "late_minutes": attendance_log.late_minutes if action_type == "check_in" else None,
                        "work_hours": attendance_log.work_hours if action_type == "check_out" else None,
                        "camera": camera_name
                    })

            finally:
                db.close()
        except Exception as e:
            logger.error(f"Attendance callback error: {e}", exc_info=True)

    # Try DeepStream first, fall back to OpenCV
    use_deepstream = True
    try:
        from .services.deepstream_stream import DeepStreamManager, PYDS_AVAILABLE
        if not PYDS_AVAILABLE:
            raise ImportError("pyds not available")

        app.state.stream = DeepStreamManager(
            cameras=enabled_cameras,
            frame_skip=settings.frame_skip,
            recognizer=app.state.recognizer,
            alert_callback=attendance_callback  # Using attendance callback
        )

        # Initialize detector for enrollment
        from .core import FaceDetector
        app.state.detector = FaceDetector(
            model_name=settings.recognition_model,
            min_confidence=settings.detection_confidence,
            use_gpu=settings.use_gpu,
            use_fp16=settings.use_fp16
        )
        app.state.processor = None
        logger.info(f"Using DeepStream pipeline with {len(enabled_cameras)} cameras")

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
            alert_callback=attendance_callback
        )
        app.state.stream.set_processor(app.state.processor)
        logger.info("Using OpenCV stream with ONNX detection")

    # Get camera info
    info = await app.state.camera.get_device_info()
    if info:
        logger.info(f"Connected to {info.model} (FW: {info.firmware})")

    # Auto-start stream
    if app.state.stream.start():
        logger.info("Attendance cameras auto-started")
    else:
        logger.warning("Failed to auto-start cameras")

    yield

    # Shutdown
    logger.info("Shutting down Employee Attendance System...")
    app.state.stream.stop()
    await app.state.camera.close()
    app.state.recognizer.save()


# Create FastAPI app
app = FastAPI(
    title="Employee Attendance System",
    description="Face recognition based employee attendance tracking with first-in/last-out logic",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=True
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5174",
        "http://localhost:3000",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(api_router, prefix="/api")

# Serve static files (frontend build)
static_path = Path(__file__).parent.parent.parent / "frontend" / "dist"
if static_path.exists():
    app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")
