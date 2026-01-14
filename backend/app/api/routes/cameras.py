"""
Camera management API routes.
CRUD operations for multi-camera support.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import cv2
import logging

from ...models.database import get_db, Camera, User
from ..deps import get_current_active_user, require_admin

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic schemas
class CameraCreate(BaseModel):
    """Schema for creating a new camera."""
    name: str = Field(..., min_length=1, max_length=100, description="Camera name")
    ip_address: str = Field(..., description="Camera IP address")
    port: int = Field(default=554, ge=1, le=65535, description="RTSP port")
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=255)
    stream_quality: str = Field(default="third", description="main/sub/third")
    enabled: bool = Field(default=True)
    detection_enabled: bool = Field(default=True)
    detection_confidence: Optional[float] = Field(default=None, ge=0.1, le=1.0)
    recognition_threshold: Optional[float] = Field(default=None, ge=0.1, le=1.0)
    frame_skip: Optional[int] = Field(default=None, ge=1, le=10)
    location: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None)


class CameraUpdate(BaseModel):
    """Schema for updating a camera."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    ip_address: Optional[str] = Field(default=None)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    username: Optional[str] = Field(default=None, min_length=1, max_length=100)
    password: Optional[str] = Field(default=None, min_length=1, max_length=255)
    stream_quality: Optional[str] = Field(default=None)
    enabled: Optional[bool] = Field(default=None)
    detection_enabled: Optional[bool] = Field(default=None)
    detection_confidence: Optional[float] = Field(default=None, ge=0.1, le=1.0)
    recognition_threshold: Optional[float] = Field(default=None, ge=0.1, le=1.0)
    frame_skip: Optional[int] = Field(default=None, ge=1, le=10)
    location: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None)


class CameraResponse(BaseModel):
    """Schema for camera response."""
    id: int
    name: str
    ip_address: str
    port: int
    username: str
    stream_quality: str
    enabled: bool
    detection_enabled: bool
    detection_confidence: Optional[float]
    recognition_threshold: Optional[float]
    frame_skip: Optional[int]
    is_online: bool
    last_seen: Optional[datetime]
    current_fps: Optional[float]
    error_message: Optional[str]
    location: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    # Derived fields
    display_status: str
    quality_description: str

    class Config:
        from_attributes = True


class StreamQualityOption(BaseModel):
    """Schema for stream quality options."""
    value: str
    label: str
    description: str


def camera_to_response(camera: Camera) -> dict:
    """Convert Camera model to response dict."""
    return {
        "id": camera.id,
        "name": camera.name,
        "ip_address": camera.ip_address,
        "port": camera.port,
        "username": camera.username,
        "stream_quality": camera.stream_quality,
        "enabled": camera.enabled,
        "detection_enabled": camera.detection_enabled,
        "detection_confidence": camera.detection_confidence,
        "recognition_threshold": camera.recognition_threshold,
        "frame_skip": camera.frame_skip,
        "is_online": camera.is_online,
        "last_seen": camera.last_seen,
        "current_fps": camera.current_fps,
        "error_message": camera.error_message,
        "location": camera.location,
        "notes": camera.notes,
        "created_at": camera.created_at,
        "updated_at": camera.updated_at,
        "display_status": camera.display_status,
        "quality_description": Camera.QUALITY_DESCRIPTIONS.get(
            camera.stream_quality, "Unknown"
        ),
    }


@router.get("/", response_model=List[dict])
async def list_cameras(
    enabled_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all cameras.

    Args:
        enabled_only: If true, only return enabled cameras
    """
    query = db.query(Camera)
    if enabled_only:
        query = query.filter(Camera.enabled == True)
    cameras = query.order_by(Camera.id).all()
    return [camera_to_response(c) for c in cameras]


@router.get("/quality-options", response_model=List[StreamQualityOption])
async def get_stream_quality_options(
    current_user: User = Depends(get_current_active_user)
):
    """Get available stream quality options for Hikvision cameras."""
    return [
        {
            "value": "third",
            "label": "Low (480p)",
            "description": "Recommended for AI processing - lowest latency"
        },
        {
            "value": "sub",
            "label": "Medium (720p)",
            "description": "Balanced quality and performance"
        },
        {
            "value": "main",
            "label": "High (4K/1080p)",
            "description": "Highest quality - may impact performance"
        },
    ]


@router.post("/", response_model=dict, status_code=201)
async def create_camera(
    camera_data: CameraCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Add a new camera.

    Validates stream quality and creates the camera record.
    """
    # Validate stream quality
    if camera_data.stream_quality not in Camera.STREAM_CHANNELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stream_quality. Must be one of: {list(Camera.STREAM_CHANNELS.keys())}"
        )

    # Check for duplicate IP
    existing = db.query(Camera).filter(
        Camera.ip_address == camera_data.ip_address
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Camera with IP {camera_data.ip_address} already exists"
        )

    # Create camera
    camera = Camera(
        name=camera_data.name,
        ip_address=camera_data.ip_address,
        port=camera_data.port,
        username=camera_data.username,
        password=camera_data.password,
        stream_quality=camera_data.stream_quality,
        enabled=camera_data.enabled,
        detection_enabled=camera_data.detection_enabled,
        detection_confidence=camera_data.detection_confidence,
        recognition_threshold=camera_data.recognition_threshold,
        frame_skip=camera_data.frame_skip,
        location=camera_data.location,
        notes=camera_data.notes,
    )

    db.add(camera)
    db.commit()
    db.refresh(camera)

    logger.info(f"Camera created: {camera.name} ({camera.ip_address})")
    return camera_to_response(camera)


@router.get("/{camera_id}", response_model=dict)
async def get_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific camera by ID."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera_to_response(camera)


@router.put("/{camera_id}", response_model=dict)
async def update_camera(
    camera_id: int,
    camera_data: CameraUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Update a camera.

    Only provided fields will be updated.
    """
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Validate stream quality if provided
    if camera_data.stream_quality and camera_data.stream_quality not in Camera.STREAM_CHANNELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stream_quality. Must be one of: {list(Camera.STREAM_CHANNELS.keys())}"
        )

    # Check for duplicate IP if changing
    if camera_data.ip_address and camera_data.ip_address != camera.ip_address:
        existing = db.query(Camera).filter(
            Camera.ip_address == camera_data.ip_address,
            Camera.id != camera_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Camera with IP {camera_data.ip_address} already exists"
            )

    # Update only provided fields
    update_data = camera_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(camera, field, value)

    db.commit()
    db.refresh(camera)

    logger.info(f"Camera updated: {camera.name} ({camera.ip_address})")
    return camera_to_response(camera)


@router.delete("/{camera_id}")
async def delete_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Delete a camera."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    camera_name = camera.name
    camera_ip = camera.ip_address

    db.delete(camera)
    db.commit()

    logger.info(f"Camera deleted: {camera_name} ({camera_ip})")
    return {"message": f"Camera '{camera_name}' deleted successfully"}


@router.post("/{camera_id}/test")
async def test_camera_connection(
    camera_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Test camera connection.

    Attempts to open the RTSP stream and grab a frame.
    Updates camera online status based on result.
    """
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    rtsp_url = camera.rtsp_url
    logger.info(f"Testing camera {camera.name}: {camera.ip_address}")

    try:
        # Try to open stream with timeout
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)

        if not cap.isOpened():
            camera.is_online = False
            camera.error_message = "Failed to open RTSP stream"
            db.commit()
            return {
                "success": False,
                "message": "Failed to open RTSP stream",
                "camera_id": camera_id
            }

        # Try to grab a frame
        ret, frame = cap.read()
        cap.release()

        if ret and frame is not None:
            camera.is_online = True
            camera.last_seen = datetime.utcnow()
            camera.error_message = None
            db.commit()

            height, width = frame.shape[:2]
            return {
                "success": True,
                "message": "Camera connection successful",
                "camera_id": camera_id,
                "resolution": f"{width}x{height}",
                "stream_quality": camera.stream_quality
            }
        else:
            camera.is_online = False
            camera.error_message = "Failed to read frame"
            db.commit()
            return {
                "success": False,
                "message": "Connected but failed to read frame",
                "camera_id": camera_id
            }

    except Exception as e:
        camera.is_online = False
        camera.error_message = str(e)
        db.commit()
        logger.error(f"Camera test failed: {e}")
        return {
            "success": False,
            "message": f"Connection error: {str(e)}",
            "camera_id": camera_id
        }


@router.get("/{camera_id}/snapshot")
async def get_camera_snapshot(
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a single snapshot from the camera.

    Returns JPEG image.
    """
    from fastapi.responses import Response

    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    rtsp_url = camera.rtsp_url

    try:
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)

        if not cap.isOpened():
            raise HTTPException(status_code=503, detail="Failed to connect to camera")

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            raise HTTPException(status_code=503, detail="Failed to capture frame")

        # Encode as JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

        # Update camera status
        camera.is_online = True
        camera.last_seen = datetime.utcnow()
        db.commit()

        return Response(
            content=buffer.tobytes(),
            media_type="image/jpeg",
            headers={"X-Camera-Name": camera.name}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Snapshot failed for camera {camera_id}: {e}")
        raise HTTPException(status_code=503, detail=f"Snapshot failed: {str(e)}")


@router.post("/{camera_id}/enable")
async def enable_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Enable a camera."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    camera.enabled = True
    db.commit()
    return {"message": f"Camera '{camera.name}' enabled", "camera_id": camera_id}


@router.post("/{camera_id}/disable")
async def disable_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Disable a camera."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    camera.enabled = False
    db.commit()
    return {"message": f"Camera '{camera.name}' disabled", "camera_id": camera_id}


@router.get("/stats/summary")
async def get_cameras_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get summary statistics for all cameras."""
    total = db.query(Camera).count()
    enabled = db.query(Camera).filter(Camera.enabled == True).count()
    online = db.query(Camera).filter(Camera.is_online == True).count()

    return {
        "total": total,
        "enabled": enabled,
        "disabled": total - enabled,
        "online": online,
        "offline": enabled - online
    }
