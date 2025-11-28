"""Stream API routes"""

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import asyncio

router = APIRouter()


@router.get("/start")
async def start_stream(request: Request):
    """Start video stream capture."""
    stream = request.app.state.stream
    success = stream.start()
    return {"success": success, "message": "Stream started" if success else "Failed to start"}


@router.get("/stop")
async def stop_stream(request: Request):
    """Stop video stream capture."""
    request.app.state.stream.stop()
    return {"success": True, "message": "Stream stopped"}


@router.get("/status")
async def stream_status(request: Request):
    """Get stream status."""
    stream = request.app.state.stream
    return {
        "running": stream.is_running,
        "fps": stream.fps,
        "subscribers": stream.subscriber_count
    }


@router.get("/mjpeg")
async def mjpeg_stream(request: Request):
    """MJPEG stream for direct browser viewing."""
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


@router.websocket("/ws")
async def websocket_stream(websocket: WebSocket, request: Request = None):
    """WebSocket stream for React frontend."""
    await websocket.accept()
    stream = websocket.app.state.stream

    if not stream.is_running:
        stream.start()

    queue = stream.subscribe()

    try:
        while True:
            frame_data = await asyncio.wait_for(queue.get(), timeout=10.0)
            jpeg = stream.encode_jpeg(frame_data.frame, quality=75)
            await websocket.send_bytes(jpeg)

    except WebSocketDisconnect:
        pass
    except asyncio.TimeoutError:
        await websocket.close(code=1000)
    finally:
        stream.unsubscribe(queue)
