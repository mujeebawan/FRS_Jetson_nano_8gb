"""System API routes"""

from fastapi import APIRouter, Request
from ..config import settings

router = APIRouter()


@router.get("/status")
async def system_status(request: Request):
    """Get system status."""
    stream = request.app.state.stream
    detector = request.app.state.detector
    recognizer = request.app.state.recognizer
    camera = request.app.state.camera

    # Get camera info
    camera_info = await camera.get_device_info()

    return {
        "stream": {
            "running": stream.is_running,
            "fps": round(stream.fps, 1),
            "subscribers": stream.subscriber_count
        },
        "recognition": {
            "persons": recognizer.person_count,
            "embeddings": recognizer.count,
            "threshold": settings.recognition_threshold
        },
        "camera": {
            "ip": settings.camera_ip,
            "model": camera_info.model if camera_info else "Unknown",
            "connected": camera_info is not None
        },
        "settings": {
            "detection_confidence": settings.detection_confidence,
            "frame_skip": settings.frame_skip,
            "motion_trigger": settings.enable_motion_trigger
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
    detection_confidence: float = None,
    recognition_threshold: float = None,
    frame_skip: int = None
):
    """Update runtime settings."""
    detector = request.app.state.detector
    recognizer = request.app.state.recognizer
    stream = request.app.state.stream

    updated = {}

    if detection_confidence is not None:
        detector.min_confidence = detection_confidence
        updated["detection_confidence"] = detection_confidence

    if recognition_threshold is not None:
        recognizer.threshold = recognition_threshold
        updated["recognition_threshold"] = recognition_threshold

    if frame_skip is not None:
        stream.frame_skip = frame_skip
        updated["frame_skip"] = frame_skip

    return {"updated": updated}
