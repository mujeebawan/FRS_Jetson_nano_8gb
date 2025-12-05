"""System API routes with resource monitoring and settings management."""

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional
from ...config import settings
from ...services.system_monitor import get_system_monitor
from ...services.settings_store import get_settings_store

router = APIRouter()


class SettingsUpdate(BaseModel):
    """Settings update request model."""
    detection_confidence: Optional[float] = None
    recognition_threshold: Optional[float] = None
    frame_skip: Optional[int] = None
    enable_motion_trigger: Optional[bool] = None
    alert_cooldown_seconds: Optional[int] = None
    video_recording_enabled: Optional[bool] = None
    video_clip_duration: Optional[int] = None  # 3-10 seconds


# Available model packs for the UI
# Each pack contains both detection (SCRFD) and recognition (ArcFace) models
AVAILABLE_MODELS = {
    "packs": [
        {
            "id": "buffalo_s",
            "name": "Buffalo S (Faster)",
            "size_mb": 88,  # FP16 size
            "fps_estimate": "25-35",
            "accuracy": "Good",
            "description": "Lightweight models optimized for real-time processing on Jetson.",
            "detection": "SCRFD det_500m",
            "recognition": "ArcFace W600K-MBF (MobileFaceNet)"
        },
        {
            "id": "buffalo_l",
            "name": "Buffalo L (More Accurate)",
            "size_mb": 171,  # FP16 size
            "fps_estimate": "15-20",
            "accuracy": "Better",
            "description": "Higher accuracy models with deeper networks. More GPU memory required.",
            "detection": "SCRFD det_10g",
            "recognition": "ArcFace W600K-R50 (ResNet50)"
        },
    ]
}


@router.get("/status")
async def system_status(request: Request):
    """Get system status including resource utilization."""
    stream = request.app.state.stream
    detector = request.app.state.detector
    recognizer = request.app.state.recognizer
    camera = request.app.state.camera

    # Get camera info
    camera_info = await camera.get_device_info()

    # Get stream stats including motion
    stream_stats = stream.get_stats() if hasattr(stream, 'get_stats') else {}

    return {
        "stream": {
            "running": stream.is_running,
            "fps": round(stream.fps, 1),
            "subscribers": stream.subscriber_count,
            "motion_active": stream.motion_active if hasattr(stream, 'motion_active') else False,
            "processed_frames": stream_stats.get("processed_frames", 0),
            "skipped_frames": stream_stats.get("skipped_frames", 0)
        },
        "recognition": {
            "persons": recognizer.person_count,
            "embeddings": recognizer.count,
            "threshold": recognizer.threshold if hasattr(recognizer, 'threshold') else settings.recognition_threshold
        },
        "detection": {
            "confidence": detector.min_confidence if hasattr(detector, 'min_confidence') else settings.detection_confidence,
            "model": detector.model_name if hasattr(detector, 'model_name') else settings.recognition_model
        },
        "camera": {
            "ip": settings.camera_ip,
            "model": camera_info.model if camera_info else "Unknown",
            "connected": camera_info is not None
        },
        "settings": {
            "detection_confidence": detector.min_confidence if hasattr(detector, 'min_confidence') else settings.detection_confidence,
            "recognition_threshold": recognizer.threshold if hasattr(recognizer, 'threshold') else settings.recognition_threshold,
            "frame_skip": stream.frame_skip if hasattr(stream, 'frame_skip') else settings.frame_skip,
            "motion_trigger": settings.enable_motion_trigger,
            "model": detector.model_name if hasattr(detector, 'model_name') else settings.recognition_model
        }
    }


@router.get("/resources")
async def system_resources():
    """Get real-time system resource utilization (CPU, GPU, RAM, temperature)."""
    monitor = get_system_monitor()
    return monitor.get_stats()


@router.get("/models")
async def available_models(request: Request):
    """Get available model packs and current selection."""
    import os

    detector = request.app.state.detector
    current_model = detector.model_name if hasattr(detector, 'model_name') else settings.recognition_model

    # Check if FP16 version is being used
    use_fp16 = "_fp16" in current_model if current_model else settings.use_fp16
    base_model = current_model.replace("_fp16", "") if current_model else settings.recognition_model

    # Check which models are available on disk
    models_with_availability = []
    for pack in AVAILABLE_MODELS["packs"]:
        pack_copy = dict(pack)
        fp16_path = os.path.expanduser(f"~/.insightface/models/{pack['id']}_fp16")
        fp32_path = os.path.expanduser(f"~/.insightface/models/{pack['id']}")
        pack_copy["fp16_available"] = os.path.exists(fp16_path)
        pack_copy["fp32_available"] = os.path.exists(fp32_path)
        pack_copy["available"] = pack_copy["fp16_available"] or pack_copy["fp32_available"]
        models_with_availability.append(pack_copy)

    return {
        "packs": models_with_availability,
        "current": {
            "model": base_model,
            "using_fp16": use_fp16,
            "full_name": current_model
        }
    }


@router.get("/camera/info")
async def camera_info(request: Request):
    """Get detailed camera information."""
    camera = request.app.state.camera
    info = await camera.get_device_info()

    if not info:
        return {"error": "Camera not connected"}

    stream_info = await camera.get_stream_info(103)

    return {
        "device": {
            "model": info.model,
            "serial": info.serial_number,
            "firmware": info.firmware,
            "mac": info.mac_address
        },
        "stream": stream_info,
        "urls": {
            "main": f"rtsp://...@{settings.camera_ip}:554/Streaming/Channels/101",
            "sub": f"rtsp://...@{settings.camera_ip}:554/Streaming/Channels/102",
            "third": f"rtsp://...@{settings.camera_ip}:554/Streaming/Channels/103"
        }
    }


@router.post("/settings/update")
async def update_settings(
    request: Request,
    settings_update: SettingsUpdate = None,
    detection_confidence: float = None,
    recognition_threshold: float = None,
    frame_skip: int = None,
    enable_motion_trigger: bool = None,
    alert_cooldown_seconds: int = None,
    video_recording_enabled: bool = None,
    video_clip_duration: int = None
):
    """
    Update runtime settings.

    Settings are applied immediately to the running system without restart.
    Changes are persisted to data/settings.json and will be loaded on next startup.
    """
    detector = request.app.state.detector
    recognizer = request.app.state.recognizer
    stream = request.app.state.stream
    alert_manager = request.app.state.alert_manager
    settings_store = get_settings_store()

    # Support both body and query params
    if settings_update:
        detection_confidence = settings_update.detection_confidence or detection_confidence
        recognition_threshold = settings_update.recognition_threshold or recognition_threshold
        frame_skip = settings_update.frame_skip or frame_skip
        enable_motion_trigger = settings_update.enable_motion_trigger if settings_update.enable_motion_trigger is not None else enable_motion_trigger
        alert_cooldown_seconds = settings_update.alert_cooldown_seconds or alert_cooldown_seconds
        video_recording_enabled = settings_update.video_recording_enabled if settings_update.video_recording_enabled is not None else video_recording_enabled
        video_clip_duration = settings_update.video_clip_duration or video_clip_duration

    updated = {}
    persisted = {}
    errors = []

    # Update detection confidence
    if detection_confidence is not None:
        if 0.1 <= detection_confidence <= 1.0:
            if hasattr(detector, 'min_confidence'):
                detector.min_confidence = detection_confidence
            updated["detection_confidence"] = detection_confidence
            persisted["detection_confidence"] = detection_confidence
        else:
            errors.append("detection_confidence must be between 0.1 and 1.0")

    # Update recognition threshold
    if recognition_threshold is not None:
        if 0.1 <= recognition_threshold <= 1.0:
            if hasattr(recognizer, 'threshold'):
                recognizer.threshold = recognition_threshold
            updated["recognition_threshold"] = recognition_threshold
            persisted["recognition_threshold"] = recognition_threshold
        else:
            errors.append("recognition_threshold must be between 0.1 and 1.0")

    # Update frame skip
    if frame_skip is not None:
        if 1 <= frame_skip <= 10:
            if hasattr(stream, 'frame_skip'):
                stream.frame_skip = frame_skip
            updated["frame_skip"] = frame_skip
            persisted["frame_skip"] = frame_skip
        else:
            errors.append("frame_skip must be between 1 and 10")

    # Update motion trigger
    if enable_motion_trigger is not None:
        # This requires updating the motion trigger in stream
        if hasattr(stream, '_enable_motion_trigger'):
            stream._enable_motion_trigger = enable_motion_trigger
            if enable_motion_trigger and stream._motion_trigger:
                if not stream._motion_trigger._running:
                    stream._motion_trigger.start()
            elif not enable_motion_trigger and stream._motion_trigger:
                stream._motion_trigger.stop()
        updated["enable_motion_trigger"] = enable_motion_trigger
        persisted["enable_motion_trigger"] = enable_motion_trigger

    # Update alert cooldown
    if alert_cooldown_seconds is not None:
        if 1 <= alert_cooldown_seconds <= 300:
            if hasattr(alert_manager, '_cooldown_seconds'):
                alert_manager._cooldown_seconds = alert_cooldown_seconds
            updated["alert_cooldown_seconds"] = alert_cooldown_seconds
            persisted["alert_cooldown_seconds"] = alert_cooldown_seconds
        else:
            errors.append("alert_cooldown_seconds must be between 1 and 300")

    # Update video recording enabled
    if video_recording_enabled is not None:
        video_recorder = request.app.state.video_recorder
        if video_recording_enabled:
            # Enable recording - create recorder if needed
            if video_recorder is None:
                from ...services.video_recorder import VideoRecorder
                clip_duration = video_clip_duration or settings.video_clip_duration
                request.app.state.video_recorder = VideoRecorder(
                    pre_alert_seconds=float(clip_duration),
                    post_alert_seconds=float(clip_duration),
                    fps=15,
                    clips_dir=settings.clips_dir
                )
                stream.set_video_recorder(request.app.state.video_recorder)
        else:
            # Disable recording - disconnect recorder
            if video_recorder:
                stream._video_recorder = None
                request.app.state.video_recorder = None
        updated["video_recording_enabled"] = video_recording_enabled
        persisted["video_recording_enabled"] = video_recording_enabled

    # Update video clip duration
    if video_clip_duration is not None:
        if 3 <= video_clip_duration <= 10:
            video_recorder = request.app.state.video_recorder
            if video_recorder:
                video_recorder.pre_alert_seconds = float(video_clip_duration)
                video_recorder.post_alert_seconds = float(video_clip_duration)
                # Update buffer size
                video_recorder._buffer = __import__('collections').deque(
                    video_recorder._buffer,
                    maxlen=int(video_clip_duration * video_recorder.fps)
                )
            updated["video_clip_duration"] = video_clip_duration
            persisted["video_clip_duration"] = video_clip_duration
        else:
            errors.append("video_clip_duration must be between 3 and 10 seconds")

    # Persist settings to file
    if persisted:
        settings_store.update(persisted)

    response = {
        "success": len(errors) == 0,
        "updated": updated,
        "persisted": len(persisted) > 0,
        "current": {
            "detection_confidence": detector.min_confidence if hasattr(detector, 'min_confidence') else settings.detection_confidence,
            "recognition_threshold": recognizer.threshold if hasattr(recognizer, 'threshold') else settings.recognition_threshold,
            "frame_skip": stream.frame_skip if hasattr(stream, 'frame_skip') else settings.frame_skip,
            "enable_motion_trigger": stream._enable_motion_trigger if hasattr(stream, '_enable_motion_trigger') else settings.enable_motion_trigger,
            "alert_cooldown_seconds": alert_manager._cooldown_seconds if hasattr(alert_manager, '_cooldown_seconds') else settings.alert_cooldown_seconds
        }
    }

    if errors:
        response["errors"] = errors

    return response


@router.get("/settings")
async def get_current_settings(request: Request):
    """Get current runtime settings."""
    detector = request.app.state.detector
    recognizer = request.app.state.recognizer
    stream = request.app.state.stream
    alert_manager = request.app.state.alert_manager
    video_recorder = request.app.state.video_recorder

    return {
        "detection_confidence": detector.min_confidence if hasattr(detector, 'min_confidence') else settings.detection_confidence,
        "recognition_threshold": recognizer.threshold if hasattr(recognizer, 'threshold') else settings.recognition_threshold,
        "frame_skip": stream.frame_skip if hasattr(stream, 'frame_skip') else settings.frame_skip,
        "enable_motion_trigger": stream._enable_motion_trigger if hasattr(stream, '_enable_motion_trigger') else settings.enable_motion_trigger,
        "alert_cooldown_seconds": alert_manager._cooldown_seconds if hasattr(alert_manager, '_cooldown_seconds') else settings.alert_cooldown_seconds,
        "recognition_model": settings.recognition_model,
        "video_recording_enabled": video_recorder is not None,
        "video_clip_duration": int(video_recorder.pre_alert_seconds) if video_recorder else settings.video_clip_duration,
        "ranges": {
            "detection_confidence": {"min": 0.1, "max": 1.0, "step": 0.05, "default": 0.5},
            "recognition_threshold": {"min": 0.1, "max": 1.0, "step": 0.05, "default": 0.4},
            "frame_skip": {"min": 1, "max": 10, "step": 1, "default": 2},
            "alert_cooldown_seconds": {"min": 1, "max": 300, "step": 1, "default": 10},
            "video_clip_duration": {"min": 3, "max": 10, "step": 1, "default": 5}
        }
    }


@router.post("/camera/zoom")
async def camera_zoom(
    request: Request,
    action: str = "stop",
    speed: int = 50
):
    """
    Control camera optical zoom.

    Args:
        action: "in" (zoom in), "out" (zoom out), "stop" (stop zooming)
        speed: Zoom speed 1-100 (default 50)
    """
    camera = request.app.state.camera
    success = await camera.ptz_zoom(action=action, speed=speed)
    return {"success": success, "action": action}


@router.post("/camera/zoom/set")
async def camera_zoom_set(request: Request, level: int = 0):
    """
    Set absolute zoom level.

    Args:
        level: Zoom level 0-100 (0=wide, 100=max tele)
    """
    camera = request.app.state.camera
    success = await camera.ptz_zoom_absolute(zoom_level=level)
    return {"success": success, "level": level}


@router.get("/camera/ptz/status")
async def camera_ptz_status(request: Request):
    """Get current PTZ status including zoom level."""
    camera = request.app.state.camera
    status = await camera.get_ptz_status()
    return status


@router.post("/models/change")
async def change_model(
    request: Request,
    model: str = "buffalo_s",
    use_fp16: bool = True
):
    """
    Change the face detection/recognition model pack.

    This will:
    1. Stop the current stream
    2. Reinitialize the detector with the new model
    3. Restart the stream

    Args:
        model: Model pack name (buffalo_s or buffalo_l)
        use_fp16: Use FP16 optimized version if available

    Returns:
        Success status and new model info
    """
    import os
    import logging

    logger = logging.getLogger(__name__)

    # Validate model
    valid_models = ["buffalo_s", "buffalo_l"]
    if model not in valid_models:
        return {
            "success": False,
            "error": f"Invalid model. Must be one of: {valid_models}"
        }

    # Check if model exists
    model_name = f"{model}_fp16" if use_fp16 else model
    model_path = os.path.expanduser(f"~/.insightface/models/{model_name}")

    if not os.path.exists(model_path):
        # Fall back to non-FP16 if FP16 not available
        if use_fp16:
            model_name = model
            model_path = os.path.expanduser(f"~/.insightface/models/{model_name}")
            if not os.path.exists(model_path):
                return {
                    "success": False,
                    "error": f"Model {model} not found. Please download it first."
                }
        else:
            return {
                "success": False,
                "error": f"Model {model} not found. Please download it first."
            }

    stream = request.app.state.stream
    detector = request.app.state.detector
    recognizer = request.app.state.recognizer

    try:
        # Stop stream if running
        was_running = stream.is_running
        if was_running:
            logger.info("Stopping stream for model change...")
            stream.stop()  # Not async

        # Reinitialize detector with new model
        logger.info(f"Switching to model: {model_name}")
        detector.model_name = model_name
        detector._initialized = False
        detector._app = None

        # Initialize with new model
        success = detector.initialize()
        if not success:
            return {
                "success": False,
                "error": "Failed to initialize new model"
            }

        # Switch recognizer to use model-specific embeddings
        logger.info(f"Switching recognizer embeddings to model: {model_name}")
        recognizer.set_model(model_name)

        # Check if we need to regenerate embeddings
        regenerated = False
        regen_success = 0
        regen_fail = 0

        if recognizer.count == 0:
            # No embeddings for this model - regenerate from saved images
            logger.info(f"No embeddings found for {model_name}, regenerating from saved images...")

            from ...services.enrollment import EnrollmentService
            from ...models.database import get_db

            enrollment = EnrollmentService(detector=detector, recognizer=recognizer)

            # Get database session
            db = next(get_db())
            try:
                regen_success, regen_fail, errors = enrollment.regenerate_all_embeddings(db, model_name)
                regenerated = True
                if errors:
                    for err in errors[:5]:  # Log first 5 errors
                        logger.warning(f"Regeneration issue: {err}")
            finally:
                db.close()

        # Restart stream if it was running
        if was_running:
            logger.info("Restarting stream with new model...")
            stream.start()  # Not async

        # Persist model selection
        settings_store = get_settings_store()
        settings_store.update({
            "recognition_model": model,
            "use_fp16": "_fp16" in model_name
        })

        response = {
            "success": True,
            "model": model_name,
            "using_fp16": "_fp16" in model_name,
            "embeddings_count": recognizer.count,
            "persisted": True,
            "message": f"Successfully switched to {model_name}"
        }

        if regenerated:
            response["regenerated"] = True
            response["regenerated_success"] = regen_success
            response["regenerated_failed"] = regen_fail
            response["message"] = f"Switched to {model_name} and regenerated {regen_success} embeddings"

        return response

    except Exception as e:
        logger.error(f"Model change failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
