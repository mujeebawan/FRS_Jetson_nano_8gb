# Base System V2 - Implementation Plan

**Created:** 2026-01-08
**Branch:** `feature/base-system-v2`
**Goal:** Finalize base system with DeepStream integration and modular camera management

---

## Overview

Replace old single-camera stream system with DeepStream multi-camera pipeline.
Add user-friendly camera management (no code changes needed to add cameras).

```
BEFORE (Old System)                    AFTER (Base System V2)
──────────────────                     ─────────────────────
- stream.py (GStreamer + ONNX)         - DeepStream PGIE+SGIE+FAISS
- Single camera hardcoded              - Multi-camera from database
- Frame-by-frame processing            - Batch processing
- ~45 FPS single camera                - 8 cameras × 25 FPS capable
```

---

## Phase 1: Camera Database Model + API

### 1.1 Database Model (`backend/app/models/database.py`)

```python
class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)          # "Front Gate"
    ip_address = Column(String(45), nullable=False)     # "192.168.1.70"
    port = Column(Integer, default=554)                 # RTSP port
    username = Column(String(100), nullable=False)      # "admin"
    password = Column(String(100), nullable=False)      # Encrypted
    stream_quality = Column(String(20), default="sub")  # main/sub/third
    enabled = Column(Boolean, default=True)
    detection_enabled = Column(Boolean, default=True)

    # Per-camera settings (override global)
    detection_confidence = Column(Float, nullable=True)
    recognition_threshold = Column(Float, nullable=True)
    frame_skip = Column(Integer, nullable=True)

    # Status tracking
    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
```

### 1.2 API Endpoints (`backend/app/api/routes/cameras.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cameras` | GET | List all cameras |
| `/api/cameras` | POST | Add new camera |
| `/api/cameras/{id}` | GET | Get camera details |
| `/api/cameras/{id}` | PUT | Update camera |
| `/api/cameras/{id}` | DELETE | Delete camera |
| `/api/cameras/{id}/test` | POST | Test camera connection |
| `/api/cameras/{id}/snapshot` | GET | Get single frame |

### 1.3 Hikvision Stream URLs

```python
# DS-2CD7A47EWD-XZS Stream Channels:
STREAM_CHANNELS = {
    "main": "Streaming/Channels/101",    # 4K/1080p high quality
    "sub": "Streaming/Channels/102",     # 720p medium quality
    "third": "Streaming/Channels/103",   # 640x480 low quality (recommended for AI)
}

def get_rtsp_url(camera: Camera) -> str:
    channel = STREAM_CHANNELS.get(camera.stream_quality, "102")
    return f"rtsp://{camera.username}:{camera.password}@{camera.ip_address}:{camera.port}/{channel}"
```

### 1.4 Commit
```bash
git add backend/app/models/database.py backend/app/api/routes/cameras.py
git commit -m "Add camera management database model and API"
```

---

## Phase 2: Camera Management UI

### 2.1 New Component (`frontend/src/components/CameraList.tsx`)

Features:
- List cameras with status indicators (online/offline)
- Add camera form (name, IP, port, username, password, quality)
- Edit camera modal
- Delete with confirmation
- Test connection button
- Stream quality dropdown (Main 4K, Sub 720p, Third 480p)

### 2.2 Settings per Camera

- Detection confidence (or use global)
- Recognition threshold (or use global)
- Frame skip (or use global)
- Enable/disable detection

### 2.3 Commit
```bash
git add frontend/src/components/CameraList.tsx frontend/src/services/api.ts
git commit -m "Add camera management UI with stream quality selection"
```

---

## Phase 3: DeepStream Integration

### 3.1 New Stream Service (`backend/app/services/deepstream_stream.py`)

Replace `stream.py` with DeepStream-based service:

```python
class DeepStreamService:
    """
    Multi-camera streaming service using DeepStream.
    Loads cameras from database, manages pipeline lifecycle.
    """

    def __init__(self):
        self.pipeline = None
        self.cameras = []

    async def load_cameras(self):
        """Load enabled cameras from database."""

    def start(self):
        """Start DeepStream pipeline with loaded cameras."""

    def stop(self):
        """Stop pipeline gracefully."""

    def add_camera(self, camera_id: int):
        """Add camera to running pipeline (if supported)."""

    def remove_camera(self, camera_id: int):
        """Remove camera from running pipeline."""
```

### 3.2 WebSocket Streaming

Stream processed frames to frontend via WebSocket:

```python
# Per-camera WebSocket endpoints
/api/stream/ws/{camera_id}     # Single camera stream
/api/stream/ws/all             # All cameras (for grid view)
```

### 3.3 Alert Integration

Connect DeepStream face results to existing alert system:

```python
def on_face_detected(faces: List[FaceResult], camera_id: int):
    for face in faces:
        if face.is_known:
            await alert_service.create_alert(
                camera_id=camera_id,
                person_id=face.person_id,
                confidence=face.confidence,
                similarity=face.match_similarity
            )
```

### 3.4 Commit
```bash
git add backend/app/services/deepstream_stream.py backend/app/api/routes/stream.py
git commit -m "Integrate DeepStream pipeline with camera management"
```

---

## Phase 4: Multi-Camera View

### 4.1 Grid View Component (`frontend/src/components/CameraGrid.tsx`)

```
┌─────────────────────────────────────────────────────────────┐
│                      LIVE MONITORING                         │
├──────────────────────────┬──────────────────────────────────┤
│                          │                                   │
│   ┌──────────────────┐   │   ┌──────────────────┐           │
│   │   Camera 1       │   │   │   Camera 2       │           │
│   │   Front Gate     │   │   │   Back Door      │           │
│   │                  │   │   │                  │           │
│   │   [LIVE]  24 FPS │   │   │   [LIVE]  23 FPS │           │
│   └──────────────────┘   │   └──────────────────┘           │
│         [Fullscreen]     │         [Fullscreen]             │
│                          │                                   │
└──────────────────────────┴──────────────────────────────────┘
```

### 4.2 Features

- 2x2 grid for 1-4 cameras
- 2x4 grid for 5-8 cameras
- Click camera for fullscreen
- Per-camera FPS display
- Per-camera detection overlay
- Alert indicators

### 4.3 Commit
```bash
git add frontend/src/components/CameraGrid.tsx frontend/src/components/LiveStream.tsx
git commit -m "Add multi-camera grid view with fullscreen option"
```

---

## Phase 5: Finalization

### 5.1 Seed Data

Add Camera 1 on first startup:

```python
# Camera 1 - Initial seed
{
    "name": "Camera 1",
    "ip_address": "192.168.1.70",
    "port": 554,
    "username": "admin",
    "password": "Admin@123",
    "stream_quality": "third",  # 480p for AI processing
    "enabled": True
}
```

### 5.2 Clean Up

- Remove hardcoded camera settings from `config.py`
- Remove old `stream.py` (keep as `stream_legacy.py` backup)
- Update all imports

### 5.3 Documentation

- Update README.md with multi-camera info
- Update QUICKSTART.md
- Update PROGRESS.md

### 5.4 Final Commit
```bash
git add -A
git commit -m "Finalize Base System V2 - Multi-camera DeepStream integration"
```

---

## Testing Checklist

- [ ] Add camera via UI
- [ ] Edit camera settings
- [ ] Delete camera
- [ ] Test connection button works
- [ ] Stream quality changes take effect
- [ ] Grid view shows all cameras
- [ ] Fullscreen works
- [ ] Face detection works on all cameras
- [ ] Alerts fire correctly with camera_id
- [ ] Snapshots include camera info

---

## Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `backend/app/api/routes/cameras.py` | Camera CRUD API |
| `backend/app/services/deepstream_stream.py` | DeepStream stream service |
| `frontend/src/components/CameraList.tsx` | Camera management UI |
| `frontend/src/components/CameraGrid.tsx` | Multi-camera grid view |

### Modified Files
| File | Changes |
|------|---------|
| `backend/app/models/database.py` | Add Camera model |
| `backend/app/api/routes/__init__.py` | Add cameras router |
| `backend/app/config.py` | Remove hardcoded camera settings |
| `backend/app/main.py` | Initialize DeepStream service |
| `frontend/src/App.tsx` | Add Cameras tab |
| `frontend/src/services/api.ts` | Add camera API calls |
| `frontend/src/components/LiveStream.tsx` | Support camera selection |

### Removed/Archived Files
| File | Action |
|------|--------|
| `backend/app/services/stream.py` | Archive as `stream_legacy.py` |

---

## Git Strategy

Commit after each phase:
1. `Add camera management database model and API`
2. `Add camera management UI with stream quality selection`
3. `Integrate DeepStream pipeline with camera management`
4. `Add multi-camera grid view with fullscreen option`
5. `Finalize Base System V2 - Multi-camera DeepStream integration`

---

## Notes

- Hikvision DS-2CD7A47EWD-XZS streams:
  - Channel 101 (main): 4K/1080p
  - Channel 102 (sub): 720p
  - Channel 103 (third): 480p (recommended for AI)

- DeepStream batch sizes:
  - PGIE: cameras count (1-8)
  - SGIE: cameras × 8 faces

- FAISS handles 19,640 matches/sec (plenty for 8 cameras)

---

*Created: 2026-01-08*
*Author: Claude Code*
