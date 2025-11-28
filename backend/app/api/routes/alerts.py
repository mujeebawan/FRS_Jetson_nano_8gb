"""Alerts API routes"""

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import asyncio

router = APIRouter()


class Alert(BaseModel):
    id: int
    timestamp: datetime
    person_id: Optional[int]
    person_name: Optional[str]
    alert_type: str  # "known", "unknown"
    confidence: float
    acknowledged: bool = False
    snapshot_path: Optional[str] = None


# In-memory alert storage (replace with database in production)
_alerts: List[Alert] = []
_alert_subscribers: List[asyncio.Queue] = []


@router.get("/")
async def list_alerts(
    limit: int = 50,
    offset: int = 0,
    acknowledged: Optional[bool] = None
) -> List[Alert]:
    """List alerts with optional filtering."""
    filtered = _alerts
    if acknowledged is not None:
        filtered = [a for a in filtered if a.acknowledged == acknowledged]
    return filtered[offset:offset + limit]


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int):
    """Acknowledge an alert."""
    for alert in _alerts:
        if alert.id == alert_id:
            alert.acknowledged = True
            return {"success": True}
    return {"success": False, "message": "Alert not found"}


@router.delete("/{alert_id}")
async def delete_alert(alert_id: int):
    """Delete an alert."""
    global _alerts
    _alerts = [a for a in _alerts if a.id != alert_id]
    return {"success": True}


@router.websocket("/ws")
async def alert_websocket(websocket: WebSocket):
    """WebSocket for real-time alert notifications."""
    await websocket.accept()
    queue = asyncio.Queue()
    _alert_subscribers.append(queue)

    try:
        while True:
            alert = await queue.get()
            await websocket.send_json(alert.dict())
    except WebSocketDisconnect:
        pass
    finally:
        _alert_subscribers.remove(queue)


async def create_alert(
    person_id: Optional[int],
    person_name: Optional[str],
    alert_type: str,
    confidence: float,
    snapshot_path: Optional[str] = None
) -> Alert:
    """Create and broadcast a new alert."""
    alert = Alert(
        id=len(_alerts) + 1,
        timestamp=datetime.now(),
        person_id=person_id,
        person_name=person_name,
        alert_type=alert_type,
        confidence=confidence,
        snapshot_path=snapshot_path
    )
    _alerts.insert(0, alert)

    # Broadcast to subscribers
    for queue in _alert_subscribers:
        await queue.put(alert)

    return alert
