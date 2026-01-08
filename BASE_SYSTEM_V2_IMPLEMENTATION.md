# Base System V2 - Implementation Plan

**Created:** 2026-01-08
**Completed:** 2026-01-08
**Branch:** `feature/base-system-v2`
**Status:** COMPLETE

---

## Overview

Add modular camera management with database-driven configuration.
Users can add/edit/delete cameras from UI without code changes.

```
BEFORE (Old System)                    AFTER (Base System V2)
──────────────────                     ─────────────────────
- Camera hardcoded in config.py        - Cameras stored in database
- Single camera only                   - Multi-camera support (1-8)
- Settings in .env file                - Per-camera settings in DB
- No UI for camera management          - Full camera CRUD in UI
```

---

## Completed Phases

### Phase 1: Camera Database Model + API (COMPLETE)

**Commit:** `Add camera management database model and API (Phase 1)`

Files created/modified:
- `backend/app/models/database.py` - Added Camera model
- `backend/app/api/routes/cameras.py` - Full CRUD API
- `backend/app/api/routes/__init__.py` - Added cameras router
- `backend/app/main.py` - Added seed_initial_camera()

API Endpoints:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cameras/` | GET | List cameras (optional: enabled_only) |
| `/api/cameras/` | POST | Add new camera |
| `/api/cameras/{id}` | GET | Get camera details |
| `/api/cameras/{id}` | PUT | Update camera |
| `/api/cameras/{id}` | DELETE | Delete camera |
| `/api/cameras/{id}/test` | POST | Test camera connection |
| `/api/cameras/{id}/snapshot` | GET | Get single JPEG frame |
| `/api/cameras/{id}/enable` | POST | Enable camera |
| `/api/cameras/{id}/disable` | POST | Disable camera |
| `/api/cameras/quality-options` | GET | Get stream quality options |
| `/api/cameras/stats/summary` | GET | Get camera statistics |

---

### Phase 2: Camera Management UI (COMPLETE)

**Commit:** `Add camera management UI with stream quality selection (Phase 2)`

Files created/modified:
- `frontend/src/components/CameraList.tsx` - Camera management component
- `frontend/src/services/api.ts` - Added camerasApi
- `frontend/src/App.tsx` - Added Cameras tab
- `frontend/src/App.css` - Camera management styles

Features:
- List cameras with status (online/offline)
- Add camera modal with form validation
- Edit camera settings
- Delete with confirmation
- Test connection button
- Stream quality selection (Main 4K, Sub 720p, Third 480p)
- Preview snapshot for each camera
- Per-camera settings (confidence, threshold, frame_skip)

---

### Phase 3: Stream System Integration (COMPLETE)

**Commit:** `Integrate camera database with stream system (Phase 3)`

Files modified:
- `backend/app/services/stream.py` - Added camera parameter, set_camera(), switch_camera_by_id()
- `backend/app/api/routes/stream.py` - Added camera switching endpoints
- `backend/app/main.py` - Load primary camera from database
- `frontend/src/services/api.ts` - Added stream camera API

New Stream API Endpoints:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stream/camera` | GET | Get currently streaming camera |
| `/api/stream/camera/{id}` | POST | Switch to different camera |

StreamManager enhancements:
- `camera` property - Get current camera instance
- `camera_id` property - Get current camera ID
- `set_camera(camera)` - Switch cameras at runtime
- `switch_camera_by_id(id, db)` - Switch by database ID

---

### Phase 4: Multi-Camera View (COMPLETE)

**Commit:** `Add multi-camera view with grid and fullscreen modes (Phase 4)`

Files created/modified:
- `frontend/src/components/MultiCameraView.tsx` - Grid/fullscreen view
- `frontend/src/App.tsx` - Added view toggle (Single/Multi)
- `frontend/src/App.css` - Multi-camera grid styles

Features:
- Grid layouts: 1x1, 2x1, 2x2, 3x2, 4x2
- Click camera tile to switch streaming
- Fullscreen mode for any camera
- Live stream for active camera
- Snapshot preview for inactive cameras
- Active camera indicator (green badge)
- Online/offline status per camera
- Responsive design

---

### Phase 5: Finalization (COMPLETE)

**This Commit:** `Finalize Base System V2 - Camera management complete`

Seed Data:
```python
Camera 1 (auto-created on first startup):
- name: "Camera 1"
- ip_address: "192.168.1.70"
- port: 554
- username: "admin"
- password: "Admin@123"
- stream_quality: "third"  # 480p for AI
- location: "Main Entrance"
```

---

## Testing Checklist

- [x] Add camera via UI
- [x] Edit camera settings
- [x] Delete camera
- [x] Test connection button works
- [x] Stream quality changes take effect
- [x] Grid view shows all cameras
- [x] Fullscreen works
- [x] Camera switching works
- [x] Seed camera created on first run

---

## Files Summary

### New Files
| File | Purpose |
|------|---------|
| `backend/app/api/routes/cameras.py` | Camera CRUD API |
| `frontend/src/components/CameraList.tsx` | Camera management UI |
| `frontend/src/components/MultiCameraView.tsx` | Multi-camera grid view |

### Modified Files
| File | Changes |
|------|---------|
| `backend/app/models/database.py` | Added Camera model |
| `backend/app/services/stream.py` | Camera switching support |
| `backend/app/api/routes/stream.py` | Camera switching endpoints |
| `backend/app/api/routes/__init__.py` | Added cameras router |
| `backend/app/main.py` | Seed camera, load from DB |
| `frontend/src/App.tsx` | Cameras tab, view toggle |
| `frontend/src/App.css` | Camera & multi-view styles |
| `frontend/src/services/api.ts` | Camera & stream APIs |

---

## Git Commits (feature/base-system-v2)

1. `Add camera management database model and API (Phase 1)`
2. `Add camera management UI with stream quality selection (Phase 2)`
3. `Integrate camera database with stream system (Phase 3)`
4. `Add multi-camera view with grid and fullscreen modes (Phase 4)`
5. `Finalize Base System V2 - Camera management complete (Phase 5)`

---

## Notes

- Hikvision DS-2CD7A47EWD-XZS streams:
  - Channel 101 (main): 4K/1080p high quality
  - Channel 102 (sub): 720p medium quality
  - Channel 103 (third): 480p low quality (recommended for AI)

- Camera settings stored in SQLite database
- Per-camera thresholds override global settings
- Stream system reads from database, not config file
- UI allows adding cameras without code changes

---

## Next Steps (Future)

1. **DeepStream Full Integration** - Replace OpenCV streaming with DeepStream for better multi-camera performance
2. **Camera Groups** - Group cameras by location/zone
3. **Camera Recording** - Continuous recording per camera
4. **PTZ Per-Camera** - PTZ controls linked to specific cameras
5. **Analytics Dashboard** - Per-camera detection statistics

---

*Completed: 2026-01-08*
*Author: Claude Code*
