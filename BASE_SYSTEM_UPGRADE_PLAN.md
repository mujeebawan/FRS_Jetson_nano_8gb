# Base System V2 - Upgrade Plan

**Branch:** `feature/base-system-v2`
**Created:** 2025-01-05
**Purpose:** Create optimized base FRS that all product variants will inherit

---

## Vision

```
                        BASE SYSTEM V2 (this branch)
                        ────────────────────────────
                        • SCRFD_10G + ResNet100
                        • DeepStream + TensorRT
                        • Simple Known/Unknown detection
                        • Clean, minimal API
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
   SECURITY SYSTEM          ATTENDANCE SYSTEM          ACCESS CONTROL
   (Criminal detect)        (Student tracking)         (Authorized entry)
```

---

## Current State (main branch)

| Component | Current | Issue |
|-----------|---------|-------|
| Detection | SCRFD_500M (buffalo_s) | Low accuracy on hard cases (69% Hard set) |
| Recognition | MobileFaceNet | Good but not best |
| Video Decode | GStreamer + nvv4l2decoder | GPU→CPU→GPU copies |
| Inference | ONNX Runtime CUDA | 2-3x slower than TensorRT |
| Features | Many (alerts, auth, video recording) | Too complex for base |

---

## Target State (base-system-v2)

| Component | Target | Benefit |
|-----------|--------|---------|
| Detection | **SCRFD_10G_KPS** | 95.4% Easy, 82.8% Hard (+13%) |
| Recognition | **ArcFace ResNet100** | 99.80%+ LFW |
| Video Decode | **DeepStream nvv4l2decoder** | Zero-copy GPU pipeline |
| Inference | **TensorRT** | 2-3x faster |
| Features | **Core only** | Clean base for products |

---

## Upgrade Tasks

### Phase 1: Model Upgrade (No DeepStream yet)

#### 1.1 Download & Prepare Larger Models
```bash
# SCRFD_10G with keypoints
# From InsightFace model zoo

# ArcFace ResNet100
# glint360k_r100 or similar
```

#### 1.2 Update detector.py
- [ ] Change model from `buffalo_sc` to custom larger models
- [ ] Update detection size for SCRFD_10G (640x640)
- [ ] Add TensorRT engine caching

#### 1.3 Update recognizer.py
- [ ] Switch to ResNet100 backbone
- [ ] Verify 512-D embedding compatibility
- [ ] Add TensorRT engine caching

#### 1.4 Test with current GStreamer pipeline
- [ ] Verify accuracy improvement
- [ ] Measure latency impact
- [ ] Run LFW benchmark

---

### Phase 2: TensorRT Conversion

#### 2.1 Export Models to ONNX
```bash
# If not already ONNX
python export_to_onnx.py --model scrfd_10g_kps
python export_to_onnx.py --model arcface_r100
```

#### 2.2 Convert to TensorRT Engines
```bash
# Detection - INT8 (acceptable accuracy loss)
trtexec --onnx=scrfd_10g_kps.onnx \
        --int8 \
        --calib=calibration_faces/ \
        --saveEngine=scrfd_10g_kps_int8.engine

# Recognition - FP16 ONLY (preserve embedding quality)
trtexec --onnx=arcface_r100.onnx \
        --fp16 \
        --saveEngine=arcface_r100_fp16.engine
```

#### 2.3 Update Code for TensorRT
- [ ] Create TensorRT inference wrapper
- [ ] Load engines at startup
- [ ] Benchmark improvements

---

### Phase 3: DeepStream Migration

#### 3.1 Install DeepStream
```bash
# JetPack 6.1 compatible
sudo apt install deepstream-7.0
```

#### 3.2 Create DeepStream Pipeline
```
                    DeepStream Pipeline
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  nvstreammux ──▶ nvinfer (SCRFD) ──▶ nvtracker         │
│       │              TRT INT8           │               │
│       │                                 ▼               │
│       │         nvinfer (ArcFace) ◀── tracker output   │
│       │              TRT FP16           │               │
│       │                                 ▼               │
│       │                           nvdsosd              │
│       │                                 │               │
│       ▼                                 ▼               │
│   appsink ◀─────────────────────── nveglglessink       │
│   (frames)                         (display)           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### 3.3 Integration Options

**Option A: Full DeepStream Python**
- Use deepstream-python-apps
- Custom probe functions for face matching
- Native FAISS integration

**Option B: Hybrid Approach**
- DeepStream for decode + detection only
- Python for recognition + matching
- Less refactoring needed

**Recommendation:** Start with Option B, migrate to A later

---

### Phase 4: Simplify Codebase

#### 4.1 Keep (Core Features)
```
backend/
├── app/
│   ├── core/
│   │   ├── detector.py      # Face detection
│   │   └── recognizer.py    # Face recognition + FAISS
│   ├── services/
│   │   ├── stream.py        # Video capture (DeepStream)
│   │   ├── processor.py     # Detection processing
│   │   └── enrollment.py    # Person enrollment
│   ├── api/routes/
│   │   ├── stream.py        # Stream endpoints
│   │   ├── persons.py       # Person CRUD
│   │   └── system.py        # System status
│   ├── models/
│   │   └── database.py      # Person, Embedding models
│   ├── config.py
│   └── main.py
```

#### 4.2 Remove (Product-Specific Features)
```
# These move to product branches, not base
- alerts.py              → product/security-system
- video_recorder.py      → product/security-system
- motion_processor.py    → product/security-system
- auth.py, users.py      → product/security-system
- security.py, seed.py   → product/security-system
```

#### 4.3 Frontend Simplification
```
frontend/src/
├── components/
│   ├── LiveStream.tsx       # Video display
│   ├── PersonList.tsx       # Enrolled persons
│   ├── DetectionOverlay.tsx # Known/Unknown boxes
│   └── SystemStatus.tsx     # Basic status
├── pages/
│   ├── Dashboard.tsx        # Main view
│   └── Enrollment.tsx       # Enroll persons
├── services/
│   └── api.ts
└── App.tsx
```

---

## Performance Targets

| Metric | Current | Target | Method |
|--------|---------|--------|--------|
| Detection Accuracy (Hard) | 69.5% | **82.8%** | SCRFD_10G |
| Recognition Accuracy (LFW) | 99.5% | **99.8%** | ResNet100 |
| Inference Latency | 22-62ms | **8-15ms** | TensorRT |
| Throughput | 44 FPS | **80+ FPS** | DeepStream |
| Multi-camera | 1 | **4-8** | DeepStream batching |

---

## Timeline Estimate

| Phase | Tasks | Dependencies |
|-------|-------|--------------|
| Phase 1 | Model upgrade | Download models |
| Phase 2 | TensorRT conversion | Phase 1 complete |
| Phase 3 | DeepStream migration | Phase 2 complete |
| Phase 4 | Code simplification | Phase 3 tested |

---

## Files Changed/Created

### New Files
- `BASE_SYSTEM_UPGRADE_PLAN.md` (this file)
- `backend/app/core/trt_inference.py` (TensorRT wrapper)
- `backend/app/services/deepstream_pipeline.py` (DeepStream)
- `configs/deepstream/` (DeepStream configs)
- `models/tensorrt/` (TRT engines)

### Modified Files
- `backend/app/core/detector.py` (larger models)
- `backend/app/core/recognizer.py` (ResNet100)
- `backend/app/services/stream.py` (DeepStream)
- `backend/app/config.py` (new model paths)

### Removed Files (moved to products)
- `backend/app/services/alerts.py`
- `backend/app/services/video_recorder.py`
- `backend/app/services/motion_processor.py`
- `backend/app/api/routes/alerts.py`
- `backend/app/api/routes/auth.py`
- `backend/app/api/routes/users.py`
- All auth-related frontend components

---

## Product Branches (Future)

After base-system-v2 is merged to main:

```bash
# Security System (Frs_sec features)
git checkout -b product/security-system
# Add back: alerts, video recording, auth, multi-camera, watchlist

# Attendance System
git checkout -b product/attendance-system
# Add: student DB, class schedules, attendance reports, parent notifications

# Access Control
git checkout -b product/access-control
# Add: authorized list, GPIO/relay control, door logs, access denied handling
```

---

## References

- [NVIDIA DeepStream SDK](https://developer.nvidia.com/deepstream-sdk)
- [DeepStream Python Apps](https://github.com/NVIDIA-AI-IOT/deepstream_python_apps)
- [face-recognition-deepstream](https://github.com/zhouyuchong/face-recognition-deepstream)
- [InsightFace Model Zoo](https://github.com/deepinsight/insightface/tree/master/model_zoo)
- [TensorRT Documentation](https://docs.nvidia.com/deeplearning/tensorrt/)
