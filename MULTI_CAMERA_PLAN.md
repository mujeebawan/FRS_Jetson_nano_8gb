# Multi-Camera Support Implementation Plan

## Overview
Add support for multiple cameras (Hikvision + Dahua PTZ) with selectable grid layouts and unified alert system.

## Current State
- Single camera (Hikvision) hardcoded
- Single stream manager
- Single camera state in app.state

## Target State
- Multiple cameras configurable
- Dynamic grid layouts (1x1, 1x2, 2x1)
- Per-camera PTZ controls
- Combined alerts with camera identification

---

## Architecture Changes

### Backend Changes

#### 1. Camera Configuration (`backend/app/config.py`)
```python
# Add camera definitions
cameras:
  - id: "cam1"
    name: "Hikvision Main"
    type: "hikvision"
    ip: "192.168.1.64"
    username: "admin"
    password: "xxx"
    rtsp_main: "rtsp://...101"
    rtsp_sub: "rtsp://...102"
    enabled: true

  - id: "cam2"
    name: "Dahua PTZ"
    type: "dahua"
    ip: "10.1.1.68"
    username: "admin"
    password: "system123"
    rtsp_main: "rtsp://.../channel=1&subtype=0"
    rtsp_sub: "rtsp://.../channel=1&subtype=1"
    enabled: true
    ptz_enabled: true
```

#### 2. Multi-Stream Manager (`backend/app/services/multi_stream.py`)
- Manages multiple StreamManager instances
- Each camera gets its own stream + processor
- Shared detector/recognizer (GPU efficient)
- Camera-specific alert callbacks

#### 3. Updated API Routes
```
GET  /api/cameras                    - List all cameras
GET  /api/cameras/{id}/status        - Camera status
POST /api/cameras/{id}/enable        - Enable/disable camera
GET  /api/stream/{camera_id}/mjpeg   - Camera-specific stream
POST /api/cameras/{id}/ptz/{action}  - PTZ control per camera
```

#### 4. Alert Updates (`backend/app/models/database.py`)
```python
class Alert:
    ...
    camera_id: str      # NEW: Which camera detected
    camera_name: str    # NEW: Human-readable camera name
```

### Frontend Changes

#### 1. New Components
```
src/components/
├── CameraStream.tsx      # Reusable single camera component
├── CameraGrid.tsx        # Grid layout manager (1x1, 1x2, 2x1)
├── CameraSelector.tsx    # Camera enable/disable settings
├── PTZControls.tsx       # PTZ control overlay/panel
└── LayoutSelector.tsx    # Grid layout switcher
```

#### 2. Updated API Service (`src/services/api.ts`)
```typescript
// Camera management
camerasApi.list()
camerasApi.getStatus(cameraId)
camerasApi.enable(cameraId, enabled)
camerasApi.getMjpegUrl(cameraId)

// PTZ controls
ptzApi.move(cameraId, direction, speed)
ptzApi.zoom(cameraId, action)
ptzApi.stop(cameraId)
ptzApi.goToPreset(cameraId, presetId)
```

#### 3. Layout Options
```
┌─────────────────────┐  ┌──────────┬──────────┐  ┌──────────┐
│                     │  │          │          │  │          │
│    Single (1x1)     │  │   1x2    │   Grid   │  ├──────────┤
│                     │  │          │          │  │   2x1    │
└─────────────────────┘  └──────────┴──────────┘  └──────────┘
     Fullscreen            Side by Side           Stacked
```

#### 4. PTZ Controls Design
```
┌─────────────────────────────────────────┐
│  Camera Name                    [⛶] [X] │
├─────────────────────────────────────────┤
│                                         │
│              VIDEO FEED                 │
│                                         │
│   ┌───────────────────┐                 │
│   │    [↑]            │    [+] Zoom     │
│   │ [←] [●] [→]       │    [-] Zoom     │
│   │    [↓]            │                 │
│   └───────────────────┘                 │
│                                         │
└─────────────────────────────────────────┘
```

---

## Implementation Order

### Phase 1: Backend Multi-Camera Support
1. Create camera configuration model
2. Create MultiStreamManager class
3. Update API routes for camera selection
4. Add camera_id to alerts table
5. Test with both cameras

### Phase 2: Frontend Grid Layout
1. Create CameraStream component (refactor from LiveStream)
2. Create CameraGrid component with layout options
3. Add LayoutSelector to dashboard
4. Update alert list to show camera source

### Phase 3: PTZ Controls
1. Create PTZControls component
2. Implement Hikvision PTZ API integration (existing)
3. Implement Dahua PTZ API integration (new)
4. Add PTZ overlay to CameraStream

### Phase 4: Settings & Polish
1. Add camera management to settings page
2. Persist layout preference
3. Add camera-specific settings
4. Testing and refinement

---

## Camera Details

### Hikvision (cam1)
- IP: 192.168.1.64
- Type: Fixed camera with optical zoom
- PTZ: Zoom only (no pan/tilt)
- RTSP: Channels 101, 102, 103

### Dahua (cam2)
- IP: 10.1.1.68
- Type: Full PTZ (360° pan, tilt, zoom)
- PTZ: Full control + wiper
- RTSP: channel=1&subtype=0/1

---

## Network Setup
Both cameras accessible from Jetson:
- enP8p1s0: 192.168.1.100/24 (Hikvision)
- enP8p1s0: 10.1.1.100/24 (Dahua - secondary IP)

---

## Estimated Scope
- Backend: ~500-700 lines new/modified
- Frontend: ~800-1000 lines new/modified
- New files: 6-8 files
- Modified files: 10-12 files
