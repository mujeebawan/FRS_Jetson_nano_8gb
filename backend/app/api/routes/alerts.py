"""Alerts API routes - reads from database"""

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from pathlib import Path
import asyncio
import threading
import queue
import logging

from ...models.database import get_db, Alert as AlertModel, Person, User
from ..deps import get_current_active_user, require_admin

router = APIRouter()
logger = logging.getLogger(__name__)

# WebSocket subscribers for real-time alerts
_alert_subscribers: List[asyncio.Queue] = []

# Thread-safe queue for broadcasting from sync code
_broadcast_queue: queue.Queue = queue.Queue()

# Reference to the main event loop (set when first WebSocket connects)
_main_loop: Optional[asyncio.AbstractEventLoop] = None


class AlertResponse(BaseModel):
    """Alert response model matching frontend expectations."""
    id: int
    timestamp: datetime
    person_id: Optional[int]
    person_name: Optional[str]
    alert_type: str  # "known", "unknown"
    confidence: float
    acknowledged: bool = False
    snapshot_path: Optional[str] = None
    # Camera info
    camera_id: Optional[int] = None
    camera_name: Optional[str] = None
    # Extended fields
    similarity_score: Optional[float] = None
    threat_level: Optional[str] = None
    watchlist_status: Optional[str] = None
    displayed_prompt: Optional[str] = None
    guard_verified: bool = False
    guard_action: Optional[str] = None

    class Config:
        from_attributes = True


def db_alert_to_response(alert: AlertModel) -> AlertResponse:
    """Convert database Alert to response model."""
    # Determine alert_type from event_type or person_id
    if alert.person_id:
        alert_type = "known"
    else:
        alert_type = "unknown"

    return AlertResponse(
        id=alert.id,
        timestamp=alert.timestamp,
        person_id=alert.person_id,
        person_name=alert.person_name,
        alert_type=alert_type,
        confidence=alert.confidence or 0.0,
        acknowledged=alert.acknowledged,
        snapshot_path=alert.snapshot_path,
        camera_id=alert.camera_id,
        camera_name=alert.camera_name,
        similarity_score=alert.similarity_score,
        threat_level=alert.threat_level,
        watchlist_status=alert.watchlist_status,
        displayed_prompt=alert.displayed_prompt,
        guard_verified=alert.guard_verified,
        guard_action=alert.guard_action
    )


@router.get("/")
async def list_alerts(
    limit: int = 50,
    offset: int = 0,
    acknowledged: Optional[bool] = None,
    search: Optional[str] = None,
    time_range: Optional[str] = None,  # "24h", "7d", "30d", "all"
    threat_level: Optional[str] = None,
    person_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> List[AlertResponse]:
    """List alerts with optional filtering."""
    query = db.query(AlertModel)

    # Filter by acknowledged status
    if acknowledged is not None:
        query = query.filter(AlertModel.acknowledged == acknowledged)

    # Filter by search term (person name)
    if search:
        search_term = f"%{search}%"
        query = query.filter(AlertModel.person_name.ilike(search_term))

    # Filter by time range
    if time_range:
        from datetime import timedelta
        now = datetime.now()
        if time_range == "24h":
            cutoff = now - timedelta(hours=24)
        elif time_range == "7d":
            cutoff = now - timedelta(days=7)
        elif time_range == "30d":
            cutoff = now - timedelta(days=30)
        else:
            cutoff = None

        if cutoff:
            query = query.filter(AlertModel.timestamp >= cutoff)

    # Filter by threat level
    if threat_level:
        query = query.filter(AlertModel.threat_level == threat_level)

    # Filter by person
    if person_id:
        query = query.filter(AlertModel.person_id == person_id)

    alerts = (
        query.order_by(AlertModel.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [db_alert_to_response(a) for a in alerts]


@router.get("/export/csv")
async def export_alerts_csv(
    time_range: Optional[str] = None,
    search: Optional[str] = None,
    threat_level: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Export alerts to CSV file."""
    from fastapi.responses import StreamingResponse
    import csv
    import io

    query = db.query(AlertModel)

    # Apply same filters as list
    if search:
        search_term = f"%{search}%"
        query = query.filter(AlertModel.person_name.ilike(search_term))

    if time_range:
        from datetime import timedelta
        now = datetime.now()
        if time_range == "24h":
            cutoff = now - timedelta(hours=24)
        elif time_range == "7d":
            cutoff = now - timedelta(days=7)
        elif time_range == "30d":
            cutoff = now - timedelta(days=30)
        else:
            cutoff = None

        if cutoff:
            query = query.filter(AlertModel.timestamp >= cutoff)

    if threat_level:
        query = query.filter(AlertModel.threat_level == threat_level)

    alerts = query.order_by(AlertModel.timestamp.desc()).all()

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "ID", "Timestamp", "Person ID", "Person Name", "Alert Type",
        "Confidence", "Similarity Score", "Threat Level", "Watchlist Status",
        "Guard Prompt", "Guard Verified", "Guard Action", "Acknowledged"
    ])

    # Data rows
    for alert in alerts:
        writer.writerow([
            alert.id,
            alert.timestamp.strftime("%Y-%m-%d %H:%M:%S") if alert.timestamp else "",
            alert.person_id or "",
            alert.person_name or "Unknown",
            "known" if alert.person_id else "unknown",
            f"{alert.confidence:.2f}" if alert.confidence else "",
            f"{alert.similarity_score:.2f}" if alert.similarity_score else "",
            alert.threat_level or "",
            alert.watchlist_status or "",
            alert.displayed_prompt or "",
            "Yes" if alert.guard_verified else "No",
            alert.guard_action or "",
            "Yes" if alert.acknowledged else "No"
        ])

    output.seek(0)

    # Generate filename with date
    filename = f"alerts_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/recent")
async def get_recent_alerts(
    hours: int = 24,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> List[AlertResponse]:
    """Get recent alerts from the last N hours."""
    cutoff = datetime.now() - timedelta(hours=hours)
    alerts = (
        db.query(AlertModel)
        .filter(AlertModel.timestamp >= cutoff)
        .order_by(AlertModel.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [db_alert_to_response(a) for a in alerts]


@router.get("/stats")
async def get_alert_stats(
    hours: int = 24,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get alert statistics for dashboard."""
    cutoff = datetime.now() - timedelta(hours=hours)

    total = db.query(AlertModel).filter(AlertModel.timestamp >= cutoff).count()
    critical = db.query(AlertModel).filter(
        AlertModel.timestamp >= cutoff,
        AlertModel.threat_level == 'critical'
    ).count()
    high = db.query(AlertModel).filter(
        AlertModel.timestamp >= cutoff,
        AlertModel.threat_level == 'high'
    ).count()
    unverified = db.query(AlertModel).filter(
        AlertModel.timestamp >= cutoff,
        AlertModel.guard_verified == False
    ).count()
    unacknowledged = db.query(AlertModel).filter(
        AlertModel.timestamp >= cutoff,
        AlertModel.acknowledged == False
    ).count()

    return {
        "period_hours": hours,
        "total_alerts": total,
        "critical_alerts": critical,
        "high_alerts": high,
        "unverified": unverified,
        "unacknowledged": unacknowledged,
        "verified": total - unverified
    }


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    acknowledged_by: str = "admin",
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Acknowledge an alert."""
    alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
    if not alert:
        return {"success": False, "message": "Alert not found"}

    alert.acknowledged = True
    alert.acknowledged_by = acknowledged_by
    alert.acknowledged_at = datetime.now()
    db.commit()

    return {"success": True}


@router.post("/{alert_id}/verify")
async def verify_alert(
    alert_id: int,
    action: str,
    verified_by: str = "guard",
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Record guard verification of an alert."""
    alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
    if not alert:
        return {"success": False, "message": "Alert not found"}

    alert.guard_verified = True
    alert.guard_action = action
    alert.guard_verified_by = verified_by
    alert.guard_verified_at = datetime.now()
    alert.action_notes = notes
    db.commit()

    return {"success": True, "action": action}


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Delete an alert."""
    alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
    if not alert:
        return {"success": False, "message": "Alert not found"}

    db.delete(alert)
    db.commit()
    return {"success": True}


@router.websocket("/ws")
async def alert_websocket(websocket: WebSocket):
    """WebSocket for real-time alert notifications."""
    global _main_loop
    _main_loop = asyncio.get_event_loop()

    await websocket.accept()
    logger.info("Alert WebSocket client connected")
    async_queue = asyncio.Queue()
    _alert_subscribers.append(async_queue)

    try:
        while True:
            # Check for alerts from sync broadcast queue
            try:
                while not _broadcast_queue.empty():
                    alert_data = _broadcast_queue.get_nowait()
                    # Put into all subscriber queues
                    for q in _alert_subscribers:
                        await q.put(alert_data)
            except:
                pass

            # Wait for alert with timeout to allow checking broadcast queue
            try:
                alert_data = await asyncio.wait_for(async_queue.get(), timeout=0.5)
                await websocket.send_json(alert_data)
                logger.info(f"Sent alert to WebSocket: {alert_data.get('id')}")
            except asyncio.TimeoutError:
                # Just continue to check broadcast queue
                pass
    except WebSocketDisconnect:
        logger.info("Alert WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        _alert_subscribers.remove(async_queue)


async def broadcast_alert(alert: AlertModel):
    """Broadcast alert to all WebSocket subscribers (async version)."""
    alert_data = _alert_to_dict(alert)

    logger.info(f"Broadcasting alert {alert.id} to {len(_alert_subscribers)} subscribers")
    for async_queue in _alert_subscribers:
        await async_queue.put(alert_data)


def broadcast_alert_sync(alert: AlertModel):
    """Broadcast alert from synchronous code (thread-safe)."""
    alert_data = _alert_to_dict(alert)

    logger.warning(f"BROADCAST: Queuing alert {alert.id} for WebSocket (queue size before: {_broadcast_queue.qsize()})")
    _broadcast_queue.put(alert_data)
    logger.warning(f"BROADCAST: Alert {alert.id} queued (queue size after: {_broadcast_queue.qsize()})")


def _alert_to_dict(alert: AlertModel) -> dict:
    """Convert alert to dictionary for JSON serialization."""
    return {
        "id": alert.id,
        "timestamp": alert.timestamp.isoformat(),
        "person_id": alert.person_id,
        "person_name": alert.person_name,
        "alert_type": "known" if alert.person_id else "unknown",
        "confidence": alert.confidence or 0.0,
        "acknowledged": alert.acknowledged,
        "snapshot_path": alert.snapshot_path,
        "threat_level": alert.threat_level,
        "watchlist_status": alert.watchlist_status,
        "displayed_prompt": alert.displayed_prompt,
        "similarity_score": alert.similarity_score
    }


@router.get("/{alert_id}/snapshot")
async def get_alert_snapshot(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get the captured snapshot image for an alert."""
    from fastapi.responses import Response

    alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if not alert.snapshot_path:
        raise HTTPException(status_code=404, detail="No snapshot available")

    image_path = Path(alert.snapshot_path)
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Snapshot file not found")

    # Read image and return with no-cache headers
    with open(image_path, 'rb') as f:
        image_data = f.read()

    return Response(
        content=image_data,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@router.get("/{alert_id}/video")
async def get_alert_video(
    request: Request,
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the video clip for an alert (if recording was enabled).

    Returns MP4 video file with footage from before and after the alert.
    """
    from fastapi.responses import FileResponse

    # Check if alert exists
    alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Get video recorder
    video_recorder = request.app.state.video_recorder
    if not video_recorder:
        raise HTTPException(status_code=404, detail="Video recording is disabled")

    # Find the clip file
    clip_path = video_recorder.get_clip_path(alert_id)
    if not clip_path or not clip_path.exists():
        raise HTTPException(status_code=404, detail="Video clip not found for this alert")

    return FileResponse(
        path=str(clip_path),
        media_type="video/mp4",
        filename=f"alert_{alert_id}.mp4"
    )


@router.get("/{alert_id}/video/exists")
async def check_alert_video(
    request: Request,
    alert_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """Check if a video clip exists for an alert."""
    video_recorder = request.app.state.video_recorder
    if not video_recorder:
        return {"exists": False, "reason": "recording_disabled"}

    clip_path = video_recorder.get_clip_path(alert_id)
    if clip_path and clip_path.exists():
        return {
            "exists": True,
            "path": str(clip_path),
            "size_mb": round(clip_path.stat().st_size / (1024 * 1024), 2)
        }
    return {"exists": False, "reason": "not_found"}
