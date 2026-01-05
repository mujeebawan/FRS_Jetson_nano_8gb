# CV Project - Complete Technical Documentation

**Document Version:** 1.0
**Last Updated:** 2025-01-05
**Platform:** NVIDIA Jetson Orin Nano 8GB
**Author:** Auto-generated Analysis

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [AI Models Used](#2-ai-models-used)
3. [Performance Metrics](#3-performance-metrics)
4. [Video Decoding Analysis](#4-video-decoding-analysis)
5. [Architecture Overview](#5-architecture-overview)
6. [Configuration Reference](#6-configuration-reference)
7. [Upgrade Recommendations](#7-upgrade-recommendations)

---

## 1. Project Overview

**Purpose:** Real-time Face Recognition & Detection System for edge deployment.

### Tech Stack
| Component | Technology |
|-----------|------------|
| Backend | FastAPI + Python 3.x |
| Frontend | React 19 + TypeScript + Vite |
| Database | SQLite (face_recognition.db) |
| ML Runtime | ONNX Runtime with CUDA EP |
| Face Library | InsightFace |
| Similarity Search | FAISS (CPU) |
| Video Pipeline | GStreamer + nvv4l2decoder |
| Camera | Hikvision IP Camera (RTSP) |

### Project Structure
```
CV_Project/
├── backend/                    # FastAPI Python backend
│   ├── app/
│   │   ├── core/              # detector.py, recognizer.py
│   │   ├── services/          # stream.py, processor.py, camera.py, enrollment.py
│   │   ├── api/routes/        # persons.py, stream.py, system.py
│   │   ├── models/            # database.py (SQLAlchemy)
│   │   ├── config.py          # Settings
│   │   └── main.py            # FastAPI app
│   ├── evaluate_lfw.py        # LFW benchmark script
│   ├── profile_system.py      # Performance profiler
│   └── generate_plots.py      # Visualization generator
├── frontend/                   # React + TypeScript UI
│   └── src/components/        # LiveStream, PersonList, Settings, etc.
├── data/                       # Runtime data, embeddings, DB
├── logs/                       # System logs
├── plots/                      # Evaluation visualizations
└── start.sh / stop.sh          # Startup scripts
```

---

## 2. AI Models Used

### 2.1 Face Detection Model

| Property | Value |
|----------|-------|
| **Model** | SCRFD (Sample and Computation Redistribution Face Detector) |
| **Variant** | SCRFD_500M (from buffalo_sc pack) |
| **Parameters** | ~0.5 Million |
| **FLOPs** | 0.5G |
| **Input Size** | 640x640 |
| **Output** | Bounding boxes + 5 facial landmarks |
| **Source** | InsightFace library |

### 2.2 Face Recognition Model

| Property | Value |
|----------|-------|
| **Model** | ArcFace with MobileFaceNet backbone |
| **Variant** | MBF (w600k_mbf from buffalo_sc) |
| **Parameters** | 3.4 Million |
| **FLOPs** | 0.44G |
| **Input Size** | 112x112 |
| **Embedding Dimension** | 512-D normalized vector |
| **Training Data** | WebFace600K |
| **Source** | InsightFace library |

### 2.3 Model Pack: buffalo_sc

The `buffalo_sc` is the **smallest/lightest** InsightFace model pack, optimized for edge devices:

```
Total Parameters: ~4M (Detection + Recognition)
Total FLOPs: ~0.94G per face
```

**Other Available Packs (for future upgrades):**
| Pack | Det Model | Rec Model | Size | Notes |
|------|-----------|-----------|------|-------|
| buffalo_sc | SCRFD_500M | MBF | Smallest | **Currently used** |
| buffalo_s | SCRFD_2.5G | MBF | Small | Better detection |
| buffalo_m | SCRFD_10G | ResNet50 | Medium | Balanced |
| buffalo_l | SCRFD_10G | ResNet100 | Large | Highest accuracy |

### 2.4 Similarity Search

| Property | Value |
|----------|-------|
| **Library** | FAISS (Facebook AI Similarity Search) |
| **Index Type** | IndexFlatIP (Inner Product) |
| **Metric** | Cosine Similarity |
| **Implementation** | CPU-based (faiss-cpu) |

---

## 3. Performance Metrics

### 3.1 LFW Benchmark Results (Jetson Orin Nano 8GB)

**Test Date:** 2025-12-17
**Dataset:** LFW (Labeled Faces in the Wild) - 6000 pairs

| Metric | Value |
|--------|-------|
| **Accuracy** | 97.33% |
| **Precision** | 99.82% |
| **Recall** | 94.81% |
| **F1-Score** | 97.25% |
| **Best Threshold** | 0.21 |
| **Evaluated Pairs** | 5982 / 6000 |

### 3.2 Confusion Matrix

```
                    Predicted
                 Positive  Negative
Actual Positive    2834       155      (Same person pairs)
Actual Negative       5      2988      (Different person pairs)

TP: 2834 | FP: 5 | FN: 155 | TN: 2988
```

### 3.3 Threshold Analysis

| Threshold | Accuracy | Precision | Recall | F1-Score |
|-----------|----------|-----------|--------|----------|
| 0.21 (best) | 97.33% | 99.82% | 94.81% | 97.25% |
| 0.30 | 97.07% | 99.96% | 94.18% | 96.99% |
| 0.35 | 96.71% | 100.0% | 93.41% | 96.59% |
| 0.40 | 95.45% | 100.0% | 90.90% | 95.23% |
| 0.50 | 90.42% | 100.0% | 80.83% | 89.40% |

### 3.4 Inference Performance (Real-time)

**Profiling Results (50 iterations, 640x480 input):**

| Metric | Value |
|--------|-------|
| **Avg Inference Time** | 22.82 ms/frame |
| **Min Inference Time** | 14.80 ms |
| **Max Inference Time** | 41.76 ms |
| **Std Deviation** | 6.62 ms |
| **Throughput** | 43.82 FPS |

**LFW Benchmark Inference (6000 pairs):**

| Metric | Value |
|--------|-------|
| **Avg Inference Time** | 61.93 ms/pair |
| **Throughput** | 16.15 FPS |

### 3.5 System Resource Utilization

| Resource | Average | Maximum |
|----------|---------|---------|
| **CPU Utilization** | 33.3% | 40.7% |
| **GPU Utilization** | 69.3% | 98.1% |
| **RAM Usage** | 5567 MB | 5570 MB |
| **Power Consumption** | 9.14 W | 10.32 W |
| **Efficiency** | ~2.85 FPS/Watt | - |

### 3.6 Hardware Specifications

| Component | Specification |
|-----------|---------------|
| **Device** | Jetson Orin Nano 8GB |
| **CPU** | 6-core ARM Cortex-A78AE @ 1.73 GHz |
| **GPU** | Ampere, 1024 CUDA cores |
| **RAM** | 8GB unified LPDDR5 |
| **Power Mode** | MAXN_SUPER (15W) |
| **L4T Version** | R36 (REVISION 4.7) |
| **JetPack** | 6.1 |
| **CUDA** | 12.6 |

---

## 4. Video Decoding Analysis

### 4.1 Current Implementation

**Method:** GStreamer with nvv4l2decoder (Hardware-accelerated)

```python
# Current GStreamer Pipeline (stream.py:121-132)
gst_pipeline = (
    f"rtspsrc location={url} latency=0 drop-on-latency=true ! "
    "rtph264depay ! h264parse ! "
    "nvv4l2decoder enable-max-performance=true ! "
    "nvvidconv ! "
    "video/x-raw,format=BGRx ! "
    "videoconvert ! "
    "video/x-raw,format=BGR ! "
    "appsink sync=false max-buffers=1 drop=true"
)
```

**Pipeline Components:**
| Element | Purpose |
|---------|---------|
| rtspsrc | RTSP stream source with low latency |
| rtph264depay | Extracts H.264 from RTP packets |
| h264parse | Parses H.264 NAL units |
| **nvv4l2decoder** | **Hardware H.264 decoding (NVDEC)** |
| nvvidconv | Hardware color space conversion |
| videoconvert | Final BGR conversion for OpenCV |
| appsink | Delivers frames to application |

### 4.2 NVIDIA Video Decoding Options Comparison

| Option | Abstraction Level | Hardware Used | Best For |
|--------|------------------|---------------|----------|
| **nvv4l2decoder** (GStreamer) | Medium | NVDEC | **General video apps** |
| **DeepStream SDK** | High | NVDEC + TensorRT | Full AI pipelines |
| **Jetson Multimedia API** | Low | NVDEC | Maximum control |
| **CUDA Video Codec SDK** | Low | NVDEC | Custom implementations |

### 4.3 What NVIDIA Recommends

**For AI/Vision Applications: DeepStream SDK**

DeepStream is NVIDIA's official recommendation for video analytics:
- End-to-end optimized pipeline
- Native TensorRT integration
- Multi-stream support (up to 1024 decode instances)
- Built-in tracking, batching, metadata handling
- Zero-copy GPU memory paths

**Key Insight:** All options use the **same NVDEC hardware decoder**. The difference is in:
1. Pipeline optimization
2. Memory management
3. Integration with inference

### 4.4 Your Current Approach vs DeepStream

| Aspect | Current (GStreamer) | DeepStream |
|--------|---------------------|------------|
| **Hardware Decoder** | NVDEC (nvv4l2decoder) | NVDEC (same) |
| **Memory Path** | GPU→CPU→GPU (for inference) | GPU→GPU (zero-copy) |
| **Batching** | Manual | Native support |
| **Multi-stream** | Manual threading | Built-in |
| **TensorRT** | Via ONNX Runtime | Native integration |
| **Complexity** | Lower | Higher learning curve |
| **Flexibility** | High | Framework-bound |

### 4.5 Decoding Performance Characteristics

| Codec | NVDEC Support | Typical Performance |
|-------|---------------|---------------------|
| H.264/AVC | Full HW | Up to 4K@120fps |
| H.265/HEVC | Full HW | Up to 8K@30fps |
| AV1 | Partial | Up to 4K@60fps |
| VP9 | Full HW | Up to 8K@30fps |

**Current Camera Stream Settings:**
```
Main Stream: Channel 101 (Full resolution)
Sub Stream:  Channel 102 (Lower resolution) ← CURRENTLY USED
Third Stream: Channel 103 (720p - recommended for AI)
```

---

## 5. Architecture Overview

### 5.1 Data Flow

```
┌─────────────┐    RTSP     ┌──────────────┐    Frames    ┌────────────┐
│  IP Camera  │ ──────────▶ │  GStreamer   │ ──────────▶  │  Capture   │
│  (Hikvision)│   H.264     │ nvv4l2decoder│   BGR        │   Thread   │
└─────────────┘             └──────────────┘              └─────┬──────┘
                                                                │
                            ┌───────────────────────────────────┘
                            ▼
┌─────────────┐    Queue    ┌──────────────┐   Embeddings  ┌────────────┐
│  Process    │ ◀────────── │   SCRFD      │ ────────────▶ │  ArcFace   │
│   Thread    │             │  Detection   │               │ Recognition│
└──────┬──────┘             └──────────────┘               └─────┬──────┘
       │                                                         │
       │ Frame with                               ┌───────────────┘
       │ Detections                               ▼
       │                    ┌──────────────┐   Similarity  ┌────────────┐
       └──────────────────▶ │    FAISS     │ ◀──────────── │ 512-D Vec  │
                            │    Index     │    Search     │ Embeddings │
                            └──────┬───────┘               └────────────┘
                                   │
                                   ▼ Match Results
                            ┌──────────────┐
                            │   FastAPI    │
                            │   Backend    │
                            └──────┬───────┘
                                   │ MJPEG/JSON
                                   ▼
                            ┌──────────────┐
                            │    React     │
                            │   Frontend   │
                            └──────────────┘
```

### 5.2 Threading Model

```
Main Thread        Capture Thread       Process Thread
     │                   │                    │
     │ ◀─── start() ─────│                    │
     │                   │                    │
     │              read frame ◀───── RTSP ───│
     │                   │                    │
     │                   │──── queue ────────▶│
     │                   │                    │
     │                   │               detect faces
     │                   │               extract embeddings
     │                   │               match FAISS
     │                   │                    │
     │                   │◀── detections ─────│
     │                   │                    │
     │              draw overlays             │
     │                   │                    │
     │ ◀── broadcast ────│                    │
     │                   │                    │
```

---

## 6. Configuration Reference

### 6.1 Default Settings (config.py)

```python
# Detection & Recognition
detection_confidence: float = 0.5     # Min face detection confidence
recognition_threshold: float = 0.4   # Min similarity for match
frame_skip: int = 2                  # Process every Nth frame
max_faces: int = 5                   # Max faces per frame

# Model Configuration
recognition_model: str = "buffalo_sc"  # Smallest model pack
use_fp16: bool = False                 # FP32 for compatibility
use_gpu: bool = True                   # GPU acceleration

# Stream Configuration
process_stream: str = "sub"            # Use sub-stream (lower res)
```

### 6.2 Runtime Settings (data/settings.json)

```json
{
  "detection_confidence": 0.5,
  "recognition_threshold": 0.4,
  "frame_skip": 2
}
```

### 6.3 Threshold Tuning Guide

| Use Case | Detection Conf | Recognition Thresh | Frame Skip |
|----------|----------------|-------------------|------------|
| High Security | 0.7 | 0.5 | 1 |
| Balanced | 0.5 | 0.4 | 2 |
| High Recall | 0.3 | 0.3 | 2 |
| Performance | 0.5 | 0.4 | 3-4 |

---

## 7. Upgrade Recommendations

### 7.1 Priority 1: DeepStream Migration (Highest Impact)

**Why:** Eliminates GPU→CPU→GPU memory copies, adds zero-copy pipeline.

**Expected Gains:**
- 30-50% latency reduction
- Multi-stream support (4-8 cameras)
- Native TensorRT integration

**Implementation Path:**
1. Install DeepStream 7.0+ on JetPack 6.1
2. Create custom `nvinfer` config for SCRFD/ArcFace
3. Use `nvtracker` for face tracking (reduce re-detection)
4. Replace GStreamer pipeline with DeepStream elements

### 7.2 Priority 2: TensorRT Model Optimization

**Why:** Current ONNX Runtime CUDA is 2-3x slower than TensorRT.

**Expected Gains:**
- 2-3x faster inference
- Lower power consumption
- FP16/INT8 quantization options

**Implementation Path:**
1. Export SCRFD/ArcFace to TensorRT engines
2. Use `trtexec` for optimization
3. Integrate with DeepStream `nvinfer` or standalone

### 7.3 Priority 3: Model Upgrades

| Current | Upgrade To | Benefit |
|---------|------------|---------|
| buffalo_sc | buffalo_s | +1-2% accuracy |
| buffalo_sc | buffalo_l | +3-5% accuracy |
| FAISS CPU | FAISS GPU | Faster for >1000 faces |

### 7.4 Priority 4: Pipeline Optimizations

| Optimization | Impact | Difficulty |
|--------------|--------|------------|
| Face tracking (DeepSORT) | Reduce detection calls | Medium |
| Batch inference | Higher throughput | Medium |
| Async processing | Lower latency | Low |
| Memory pooling | Reduce allocations | Medium |

### 7.5 Performance Targets (Post-Upgrade)

| Metric | Current | Target (DeepStream+TRT) |
|--------|---------|-------------------------|
| Latency | 22-62 ms | 8-15 ms |
| Throughput | ~44 FPS | 80-120 FPS |
| Multi-stream | 1 camera | 4-8 cameras |
| Power | 9.14 W | 7-8 W |

---

## Quick Reference Commands

```bash
# Start the system
./start.sh

# Stop the system
./stop.sh

# Run LFW benchmark
cd backend && python evaluate_lfw.py

# Run system profiling
cd backend && python profile_system.py

# Generate plots
cd backend && python generate_plots.py

# Check GPU utilization
tegrastats

# Check CUDA version
nvcc --version
```

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-05 | Initial documentation |

---

**Sources & References:**
- [NVIDIA DeepStream SDK](https://developer.nvidia.com/deepstream-sdk)
- [DeepStream Documentation](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_Performance.html)
- [Gst-nvvideo4linux2 Plugin](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_plugin_gst-nvvideo4linux2.html)
- [InsightFace GitHub](https://github.com/deepinsight/insightface)
