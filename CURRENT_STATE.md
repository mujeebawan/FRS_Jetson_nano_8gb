# Face Recognition Security System - Current State

**Last Updated:** January 9, 2026
**Branch:** `feature/base-system-v2`

## System Overview

Real-time face recognition security system running on Jetson Orin Nano 8GB with:
- 2 Hikvision IP cameras (192.168.1.70, 192.168.1.72)
- DeepStream 7.1 for hardware-accelerated H264 video decoding
- TensorRT for face detection (SCRFD) and recognition (ArcFace)
- FAISS for fast embedding matching
- React frontend with multi-camera view

## Current Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        RTSP Cameras                              │
│              Camera 1 (192.168.1.70)                            │
│              Camera 2 (192.168.1.72)                            │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                   DeepStream Pipeline                            │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐     │
│  │ rtspsrc  │──▶│ nvv4l2   │──▶│ streammux│──▶│  tiler   │     │
│  │ (H264)   │   │ decoder  │   │ (batch)  │   │ (960x540)│     │
│  └──────────┘   └──────────┘   └──────────┘   └────┬─────┘     │
└────────────────────────────────────────────────────┼────────────┘
                                                     │
┌────────────────────────────────────────────────────▼────────────┐
│              TensorRT Process (Separate CUDA Context)           │
│  ┌─────────────────────┐    ┌─────────────────────┐            │
│  │   SCRFD Detection   │───▶│  ArcFace Recognition │            │
│  │   (~35ms, batch 2)  │    │  (~20ms, batch 32)   │            │
│  └─────────────────────┘    └──────────┬──────────┘            │
└─────────────────────────────────────────┼───────────────────────┘
                                          │
┌─────────────────────────────────────────▼───────────────────────┐
│                     FAISS Matching (~6ms)                        │
│                     CPU fallback (GPU init failed)               │
└─────────────────────────────────────────────────────────────────┘
```

## Performance Metrics (Achieved)

| Component | Performance | Notes |
|-----------|-------------|-------|
| Video Decode | 25 FPS | DeepStream nvv4l2decoder |
| Face Detection | ~35ms | TensorRT SCRFD (batch 2) |
| Face Recognition | ~20ms | TensorRT ArcFace (batch 32) |
| FAISS Matching | ~6ms | CPU mode (GPU init issue) |
| **Total Pipeline** | ~60ms | Per detection cycle |
| Frame Skip | 5 | Detection every 6th frame |

## Key Implementation Details

### TensorRT Separate Process Architecture

The system uses a **separate process** for TensorRT inference to avoid CUDA context conflicts between DeepStream and pycuda:

- **Main Process**: DeepStream pipeline (video decode, tiling)
- **Child Process**: TensorRT inference (SCRFD + ArcFace)
- **IPC**: Multiprocessing Queue with `spawn` context

Key files:
- `backend/app/services/trt_process.py` - TRT child process manager
- `backend/app/services/deepstream_stream.py` - DeepStream pipeline

### Multi-Camera Support

- Cameras are tiled into a single 1920x1080 view (2x1 grid)
- Per-camera frame extraction via cropping
- Camera selection for enrollment (camera_id parameter)

### Enrollment System

- File-based enrollment: Upload image
- Camera-based enrollment: Capture from live stream
- Embeddings stored in: `data/embeddings/embeddings_buffalo_l.pkl`
- Reference images in: `data/reference_images/`

## Known Issues

### 1. Camera Enrollment Preview Shows Tiled View (OPEN)

**Priority:** High
**Status:** In Progress

**Problem:** When enrolling from camera, the preview modal shows the tiled multi-camera view instead of the selected single camera view.

**Root Cause:** The MJPEG endpoint `/stream/mjpeg/camera/{id}` exists but:
1. The preview may not be loading the single-camera stream correctly
2. The cropping from tiled view may not match frontend expectations

**Affected Files:**
- `frontend/src/components/PersonList.tsx` - Camera selector and preview
- `backend/app/api/routes/stream.py` - Single camera MJPEG endpoint
- `backend/app/services/deepstream_stream.py` - `get_camera_frame()` method

**Expected Behavior:**
- User selects Camera 1 → Preview shows ONLY Camera 1's view
- User selects Camera 2 → Preview shows ONLY Camera 2's view
- Enrollment captures from selected camera only (backend works correctly)

**Workaround:** The backend API correctly captures from the selected camera even though preview shows tiled view.

### 2. FAISS GPU Initialization Fails (LOW PRIORITY)

**Error:** `module 'faiss._swigfaiss' has no attribute 'delete_GpuResourcesVector'`

**Impact:** Falls back to CPU FAISS, still fast enough (~6ms)

**Cause:** FAISS-GPU compatibility issue with Jetson

### 3. TensorRT Engine Warnings (COSMETIC)

**Warning:** "Using an engine plan file across different models of devices is not recommended"

**Impact:** None - engines work correctly

## File Structure

```
Frs_sec/
├── backend/
│   ├── app/
│   │   ├── api/routes/
│   │   │   ├── persons.py      # Enrollment endpoints
│   │   │   ├── stream.py       # Video streaming endpoints
│   │   │   └── ...
│   │   ├── core/
│   │   │   ├── recognizer.py   # FAISS matching
│   │   │   └── trt_inference.py # TensorRT wrapper
│   │   ├── services/
│   │   │   ├── deepstream_stream.py  # DeepStream pipeline
│   │   │   └── trt_process.py        # TRT child process
│   │   └── main.py             # FastAPI app
│   └── ...
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── PersonList.tsx  # Enrollment UI
│   │   │   ├── MultiCameraView.tsx
│   │   │   └── ...
│   │   └── services/api.ts     # API client
│   └── ...
├── data/
│   ├── embeddings/             # Face embeddings
│   ├── reference_images/       # Enrollment photos
│   ├── tensorrt_engines/       # TRT engine files
│   └── frs.db                  # SQLite database
└── configs/deepstream/         # DeepStream configs
```

## API Endpoints

### Enrollment
- `POST /api/persons/enroll` - Enroll from uploaded image
- `POST /api/persons/enroll-from-camera?name=X&camera_id=N` - Enroll from camera N

### Streaming
- `GET /api/stream/mjpeg` - Full tiled view (all cameras)
- `GET /api/stream/mjpeg/camera/{id}` - Single camera view
- `GET /api/stream/status` - Pipeline status

### Cameras
- `GET /api/cameras/` - List all cameras
- `GET /api/cameras/?enabled_only=true` - List enabled cameras

## How to Start

```bash
cd /home/tempuser/Downloads/Frs_sec
./start.sh
```

Access:
- Frontend: http://192.168.0.245:5173
- Backend API: http://192.168.0.245:8000
- API Docs: http://192.168.0.245:8000/docs

## Next Steps (Monday)

1. **Fix camera enrollment preview** - Make preview show selected camera only
2. Test enrollment flow end-to-end
3. Verify face recognition matching works with enrolled persons
