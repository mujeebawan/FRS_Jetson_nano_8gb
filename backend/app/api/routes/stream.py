"""Stream API routes"""

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
import asyncio

from ...models.database import get_db, Camera, User
from ..deps import get_current_active_user, require_admin

router = APIRouter()


@router.get("/start")
async def start_stream(
    request: Request,
    admin: User = Depends(require_admin)
):
    """Start video stream capture (admin only)."""
    stream = request.app.state.stream
    success = stream.start()
    return {"success": success, "message": "Stream started" if success else "Failed to start"}


@router.get("/stop")
async def stop_stream(
    request: Request,
    admin: User = Depends(require_admin)
):
    """Stop video stream capture (admin only)."""
    request.app.state.stream.stop()
    return {"success": True, "message": "Stream stopped"}


@router.get("/status")
async def stream_status(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """Get stream status including camera info and motion detection stats."""
    stream = request.app.state.stream

    # Get full stats from DeepStream (includes per-camera FPS)
    stats = stream.get_stats() if hasattr(stream, 'get_stats') else {}

    response = {
        "running": stream.is_running,
        "fps": round(stream.fps, 1),
        "subscribers": stream.subscriber_count,
        "motion_active": stream.motion_active,
        "num_cameras": stats.get("num_cameras", 1),
        "faces_detected": stats.get("faces_detected", 0),
        "faces_matched": stats.get("faces_matched", 0),
        "pipeline": stats.get("pipeline", "Unknown")
    }

    # Include all cameras with per-camera FPS
    if "cameras" in stats:
        response["cameras"] = stats["cameras"]

    # Include current camera info (backward compatibility)
    if stream.camera:
        response["camera"] = {
            "id": stream.camera_id,
            "name": stream.camera.name,
            "ip_address": stream.camera.ip_address,
            "stream_quality": stream.camera.stream_quality
        }

    # Include full motion stats if available
    motion_stats = stream.motion_stats
    if motion_stats:
        response["motion"] = motion_stats

    return response


@router.post("/camera/{camera_id}")
async def switch_camera(
    camera_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Switch streaming to a different camera (admin only).

    Args:
        camera_id: ID of the camera to switch to
    """
    stream = request.app.state.stream

    # Get camera from database
    camera = db.query(Camera).filter(
        Camera.id == camera_id,
        Camera.enabled == True
    ).first()

    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found or not enabled")

    # Switch camera
    success = stream.set_camera(camera)

    return {
        "success": success,
        "message": f"Switched to camera: {camera.name}" if success else "Failed to switch camera",
        "camera": {
            "id": camera.id,
            "name": camera.name,
            "ip_address": camera.ip_address,
            "stream_quality": camera.stream_quality
        }
    }


@router.get("/camera")
async def get_current_camera(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """Get the currently active camera."""
    stream = request.app.state.stream

    if not stream.camera:
        return {"camera": None, "message": "No camera configured"}

    return {
        "camera": {
            "id": stream.camera_id,
            "name": stream.camera.name,
            "ip_address": stream.camera.ip_address,
            "stream_quality": stream.camera.stream_quality,
            "rtsp_url_masked": f"rtsp://***@{stream.camera.ip_address}:{stream.camera.port}/..."
        }
    }


@router.get("/snapshot")
async def get_snapshot(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """Get a single JPEG snapshot from the current stream (raw tiled view, without overlays)."""
    stream = request.app.state.stream

    if not stream.is_running:
        raise HTTPException(status_code=400, detail="Stream not running")

    # Get raw frame (without bounding boxes) for enrollment
    frame_data = stream.get_latest_raw_frame()
    if frame_data is None or frame_data.frame is None:
        raise HTTPException(status_code=404, detail="No frame available")

    # Encode as JPEG
    jpeg = stream.encode_jpeg(frame_data.frame, quality=90)

    return Response(content=jpeg, media_type="image/jpeg")


@router.get("/snapshot/camera/{camera_id}")
async def get_camera_snapshot(
    camera_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """Get a single JPEG snapshot from a specific camera (raw, without overlays)."""
    stream = request.app.state.stream

    if not stream.is_running:
        raise HTTPException(status_code=400, detail="Stream not running")

    # Get camera index from database ID
    camera_index = stream.get_camera_index_by_id(camera_id)
    if camera_index is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    # Get raw frame for this specific camera (no overlays)
    frame_data = stream.get_camera_raw_frame(camera_index)
    if frame_data is None or frame_data.frame is None:
        raise HTTPException(status_code=404, detail="No frame available from camera")

    # Encode as JPEG
    jpeg = stream.encode_jpeg(frame_data.frame, quality=90)

    return Response(content=jpeg, media_type="image/jpeg")


@router.get("/mjpeg")
async def mjpeg_stream(request: Request):
    """MJPEG stream for direct browser viewing (full tiled view with all cameras)."""
    stream = request.app.state.stream

    if not stream.is_running:
        stream.start()

    async def generate():
        queue = stream.subscribe()
        try:
            while True:
                try:
                    frame_data = await asyncio.wait_for(queue.get(), timeout=5.0)
                    # Use quality=65 for faster encoding, still good visual quality
                    jpeg = stream.encode_jpeg(frame_data.frame, quality=65)
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                    )
                except asyncio.TimeoutError:
                    continue
        finally:
            stream.unsubscribe(queue)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/mjpeg/camera/{camera_id}")
async def mjpeg_camera_stream(camera_id: int, request: Request):
    """MJPEG stream for a single camera (cropped from tiled view)."""
    stream = request.app.state.stream

    if not stream.is_running:
        stream.start()

    # Get camera index from database ID
    camera_index = stream.get_camera_index_by_id(camera_id)
    if camera_index is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    async def generate():
        queue = stream.subscribe()
        try:
            while True:
                try:
                    # Wait for new frame from subscription (synchronized)
                    frame_data = await asyncio.wait_for(queue.get(), timeout=5.0)
                    # Crop to single camera
                    camera_frame = stream.get_camera_frame(camera_index)
                    if camera_frame and camera_frame.frame is not None:
                        jpeg = stream.encode_jpeg(camera_frame.frame, quality=65)
                        yield (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                        )
                except asyncio.TimeoutError:
                    continue
        finally:
            stream.unsubscribe(queue)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.websocket("/ws")
async def websocket_stream(websocket: WebSocket, request: Request = None):
    """WebSocket stream for React frontend with low latency (includes overlays)."""
    await websocket.accept()
    stream = websocket.app.state.stream

    if not stream.is_running:
        stream.start()

    queue = stream.subscribe()

    try:
        while True:
            try:
                # Short timeout for responsiveness
                frame_data = await asyncio.wait_for(queue.get(), timeout=2.0)
                # Quality 60 is good balance of quality vs encoding speed
                jpeg = stream.encode_jpeg(frame_data.frame, quality=60)
                await websocket.send_bytes(jpeg)
            except asyncio.TimeoutError:
                # Continue waiting for frames
                continue

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        stream.unsubscribe(queue)


@router.websocket("/ws/raw")
async def websocket_raw_stream(websocket: WebSocket, request: Request = None):
    """
    Raw WebSocket stream WITHOUT overlays/bounding boxes.
    Used for enrollment preview - shows clean camera feed.
    """
    await websocket.accept()
    stream = websocket.app.state.stream

    if not stream.is_running:
        stream.start()

    try:
        while True:
            try:
                # Get raw frame directly (no subscription needed - just latest frame)
                await asyncio.sleep(0.033)  # ~30 FPS
                frame_data = stream.get_latest_raw_frame()
                if frame_data and frame_data.frame is not None:
                    jpeg = stream.encode_jpeg(frame_data.frame, quality=70)
                    await websocket.send_bytes(jpeg)
            except asyncio.TimeoutError:
                continue

    except WebSocketDisconnect:
        pass
    except Exception:
        pass


@router.get("/mjpeg/raw")
async def mjpeg_raw_stream(request: Request):
    """
    Raw MJPEG stream WITHOUT overlays/bounding boxes.
    Used for enrollment preview in browsers that don't support WebSocket well.
    """
    stream = request.app.state.stream

    if not stream.is_running:
        stream.start()

    async def generate():
        while True:
            try:
                await asyncio.sleep(0.033)  # ~30 FPS
                frame_data = stream.get_latest_raw_frame()
                if frame_data and frame_data.frame is not None:
                    jpeg = stream.encode_jpeg(frame_data.frame, quality=70)
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                    )
            except Exception:
                break

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/mjpeg/camera/{camera_id}/raw")
async def mjpeg_camera_raw_stream(camera_id: int, request: Request):
    """
    Raw MJPEG stream for a SINGLE camera WITHOUT overlays/bounding boxes.
    Used for enrollment preview - shows clean camera feed for face capture.
    """
    stream = request.app.state.stream

    if not stream.is_running:
        stream.start()

    # Get camera index from database ID
    camera_index = stream.get_camera_index_by_id(camera_id)
    if camera_index is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    async def generate():
        while True:
            try:
                await asyncio.sleep(0.033)  # ~30 FPS
                # Get raw frame (no overlays) for this specific camera
                camera_frame = stream.get_camera_raw_frame(camera_index)
                if camera_frame and camera_frame.frame is not None:
                    jpeg = stream.encode_jpeg(camera_frame.frame, quality=70)
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                    )
            except Exception:
                break

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
