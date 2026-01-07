# Project Progress - Face Recognition Security System

**Last Updated**: 2026-01-07
**Device**: Jetson Orin Nano 8GB
**GitHub Repo**: https://github.com/mujeebawan/FRS_Jetson_nano_8gb

## Current Status: BASE SYSTEM V2 - TensorRT Optimized

System is fully operational with TensorRT acceleration:
- **47+ FPS** with TensorRT Execution Provider (10x speedup)
- **98.23% accuracy** on LFW benchmark
- **21ms latency** end-to-end
- Default model: buffalo_l (SCRFD_10G + ResNet50)
- FP16 inference with cached TensorRT engines
- WebSocket alerts and MJPEG streaming

---

## System Configuration

| Component | Value |
|-----------|-------|
| Camera IP | 192.168.1.64 |
| Camera Model | DS-2CD7A47EWD-XZS |
| Jetson IP (WiFi) | 192.168.0.245 |
| Jetson IP (Eth) | 192.168.1.100 |
| Backend Port | 8000 |
| Frontend Port | 5173 |
| Active Model | buffalo_l (SCRFD_10G + ResNet50) |
| Inference Provider | TensorRT EP + FP16 |
| Persons Enrolled | 3 (Mujeeb, Mubashir, Zohaib) |

---

## Session Log

### Session 5 - 2026-01-07 (TensorRT EP Integration - Base System V2)

#### Major Achievements:

1. **TensorRT Execution Provider Integration**
   - Added `use_tensorrt` config option (default: True)
   - TensorRT EP with FP16 enabled for 10x speedup
   - Engine caching at `data/tensorrt_engines/`
   - Fallback chain: TensorRT → CUDA → CPU

2. **Performance Improvements**
   - Before (CUDA EP): ~4.5 FPS, 223ms latency
   - After (TensorRT EP): **47.6 FPS, 21ms latency**
   - **10.6x speedup** with no accuracy loss

3. **LFW Benchmark Results**
   - buffalo_l (SCRFD_10G + ResNet50): **98.23% accuracy @ 45 FPS**
   - buffalo_custom_500m_r50: 97.53% accuracy @ 60 FPS
   - ResNet100 broken with TensorRT FP16 (known issue)

4. **Model Selection**
   - Default changed from buffalo_s to buffalo_l
   - buffalo_l recommended for security (higher accuracy)
   - buffalo_custom_500m_r50 available for attendance (higher speed)

5. **Benchmark Scripts Added**
   - `profile_tensorrt_ep.py` - TensorRT EP profiling
   - `evaluate_lfw_trt.py` - LFW accuracy evaluation
   - `benchmark_deepstream_hybrid.py` - DeepStream comparison

#### Files Modified:

| File | Changes |
|------|---------|
| `backend/app/config.py` | Added `use_tensorrt` option, changed default to buffalo_l |
| `backend/app/core/detector.py` | TensorRT EP integration with engine caching |
| `TENSORRT_BENCHMARK_RESULTS.md` | Complete benchmark documentation |

#### TensorRT Engine Cache:

```
data/tensorrt_engines/
├── TensorrtExecutionProvider_*_det_10g_*.engine (9MB)
├── TensorrtExecutionProvider_*_w600k_r50_*.engine (72MB)
└── ... (other model engines)
```

---

### Session 4 - 2025-12-02 (Multi-Model Support & Production Ready)

#### Major Achievements:

1. **Multi-Model Support**
   - Added buffalo_l model pack alongside buffalo_s
   - Runtime model switching via Settings UI and API
   - FP16 conversion for both models with `keep_io_types=True` fix

2. **Model-Specific Embeddings**
   - Embeddings stored per-model: `embeddings_buffalo_s.pkl`, `embeddings_buffalo_l.pkl`
   - Added `set_model()` method to recognizer for switching
   - Models produce incompatible embeddings (MobileFaceNet vs ResNet50)

3. **Multi-Model Enrollment**
   - Enroll once, embeddings generated for ALL available models
   - `generate_embeddings_for_all_models()` in persons.py
   - Each enrollment creates temporary detector/recognizer for other models

4. **Multi-Model Deletion**
   - Delete once, removed from ALL model embedding files
   - `remove_person_from_all_models()` in persons.py

5. **Auto-Regeneration on Model Switch**
   - When switching to model with no embeddings, auto-regenerate from saved images
   - `regenerate_all_embeddings()` in enrollment.py
   - Uses reference images stored in `data/persons/{id}/`

6. **Settings Apply to All Models**
   - Recognition threshold preserved when switching models
   - Detection confidence applied correctly

7. **Production Ready Setup**
   - Systemd service: `/etc/systemd/system/frs.service`
   - Auto-start on boot (enabled)
   - Health endpoint: `/api/health` fixed
   - Clean restart verified with no conflicts
   - Legacy files cleaned up

8. **Documentation Updated**
   - README.md - Complete rewrite with current features
   - QUICKSTART.md - Quick reference guide
   - PROGRESS.md - This file

#### Files Created/Modified:

| File | Description |
|------|-------------|
| `backend/app/core/recognizer.py` | Model-specific embeddings, set_model() |
| `backend/app/api/routes/persons.py` | Multi-model enrollment/deletion |
| `backend/app/api/routes/system.py` | Model change with auto-regeneration |
| `backend/app/services/enrollment.py` | regenerate_all_embeddings() |
| `backend/app/api/routes/__init__.py` | Health endpoint fix |
| `scripts/convert_fp16.py` | Fixed with keep_io_types=True |
| `frs.service` | Systemd service file |
| `README.md` | Complete documentation |
| `QUICKSTART.md` | Quick start guide |

#### Model Files:

| Model | Path | Size |
|-------|------|------|
| buffalo_s_fp16 | ~/.insightface/models/buffalo_s_fp16/ | 88MB |
| buffalo_l_fp16 | ~/.insightface/models/buffalo_l_fp16/ | 171MB |

#### Embedding Files:

| File | Persons | Model |
|------|---------|-------|
| embeddings_buffalo_s.pkl | 3 | MobileFaceNet |
| embeddings_buffalo_l.pkl | 2 | ResNet50 |

Note: Zohaib's face not detected by buffalo_l model (different detection sensitivity)

---

### Session 3 - 2025-11-28 (System Settings & Resource Monitoring)

#### Achievements:
- System resource monitoring service (CPU, GPU, RAM, temp)
- Settings API with live updates
- SystemSettings React component with sliders
- Model selection UI

---

### Session 2 - 2025-11-28 (GPU Optimization)

#### Achievements:
- GPU acceleration enabled: 34.4 FPS
- FP16 model conversion
- Low-latency GStreamer pipeline
- Motion-triggered processing
- Database models (SQLAlchemy)
- Alert management system

---

### Session 1 - 2025-11-28 (Initial Setup)

#### Achievements:
- OpenCV 4.10.0 with CUDA built
- InsightFace buffalo_s loaded
- FastAPI backend created
- React frontend initialized
- Camera integration working

---

## Project Structure

```
/home/tempuser/Downloads/frs/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # API endpoints
│   │   │   ├── __init__.py      # Health endpoint
│   │   │   ├── stream.py        # Video streaming
│   │   │   ├── persons.py       # Enrollment (multi-model)
│   │   │   ├── alerts.py        # Alert management
│   │   │   └── system.py        # Settings, models, resources
│   │   ├── core/
│   │   │   ├── detector.py      # SCRFD face detection
│   │   │   └── recognizer.py    # ArcFace + FAISS (multi-model)
│   │   ├── models/
│   │   │   └── database.py      # SQLAlchemy ORM
│   │   ├── services/
│   │   │   ├── camera.py        # Hikvision ISAPI
│   │   │   ├── stream.py        # Multi-client streaming
│   │   │   ├── processor.py     # Frame processing
│   │   │   ├── alerts.py        # Alert creation
│   │   │   ├── enrollment.py    # Person enrollment
│   │   │   ├── motion_processor.py
│   │   │   └── system_monitor.py
│   │   ├── config.py
│   │   └── main.py
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── LiveStream.tsx
│       │   ├── PersonList.tsx
│       │   ├── AlertList.tsx
│       │   └── SystemSettings.tsx
│       ├── services/api.ts
│       ├── App.tsx
│       └── App.css
├── data/
│   ├── persons/                 # Enrolled person images
│   │   └── {person_id}/
│   │       └── reference.jpg
│   ├── embeddings/              # Model-specific embeddings
│   │   ├── embeddings_buffalo_s.pkl
│   │   └── embeddings_buffalo_l.pkl
│   ├── snapshots/               # Alert snapshots
│   └── frs.db                   # SQLite database
├── scripts/
│   └── convert_fp16.py
├── docs/
│   ├── PROGRESS.md              # This file
│   ├── SETUP_GUIDE.md
│   └── SYSTEM_CAPABILITIES.md
├── start.sh
├── stop.sh
├── status.sh
├── frs.service
├── QUICKSTART.md
└── README.md
```

---

## Performance Benchmarks

### Jetson Orin Nano 8GB (JetPack 6.2)

| Configuration | FPS | Latency | Accuracy | Notes |
|--------------|-----|---------|----------|-------|
| CPU only | 1-2 | 500ms+ | - | Not usable |
| CUDA EP (FP32) | 4-5 | 223ms | 98.23% | Baseline |
| **TensorRT EP (FP16) buffalo_l** | **47** | **21ms** | **98.23%** | **PRODUCTION** |
| TensorRT EP (FP16) 500m_r50 | 60 | 17ms | 97.53% | High-speed option |

### TensorRT vs CUDA EP Comparison

| Metric | CUDA EP | TensorRT EP | Improvement |
|--------|---------|-------------|-------------|
| Throughput | 4.5 FPS | 47.6 FPS | **10.6x** |
| Latency | 223ms | 21ms | **10.6x** |
| Accuracy | 98.23% | 98.23% | No loss |

---

## How to Resume Development

### Start the system:
```bash
cd /home/tempuser/Downloads/frs
./start.sh
```

### Check status:
```bash
./status.sh
```

### View logs:
```bash
tail -f /tmp/frs_backend.log
tail -f /tmp/frs_frontend.log
```

### Access:
- Frontend: http://192.168.0.245:5173
- API Docs: http://192.168.0.245:8000/docs

---

## Known Issues

1. **Zohaib not detected by buffalo_l**: The buffalo_l detection model (SCRFD 10g) has different sensitivity and may not detect some faces that buffalo_s detects. This is expected behavior due to model differences.

2. **FP16 Input Type**: Original FP16 conversion failed because models expected FP16 input tensors. Fixed by using `keep_io_types=True` in conversion.

---

## Future Enhancements

- [x] TensorRT Execution Provider (10x speedup) ✅ DONE
- [x] TensorRT engine caching ✅ DONE
- [ ] **DeepStream integration** (Phase 3 - next)
- [ ] Multi-camera support (4-8 cameras)
- [ ] Code simplification for base system (Phase 4)
- [ ] PostgreSQL for production
- [ ] Mobile app for alerts
