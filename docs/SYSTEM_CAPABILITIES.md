# System Capabilities - Jetson Orin Nano 8GB

## Hardware Specifications

| Component | Specification |
|-----------|---------------|
| **Device** | NVIDIA Jetson Orin Nano Engineering Reference Developer Kit Super |
| **RAM** | 7.4 GB total (shared CPU/GPU) |
| **Swap** | 3.7 GB (zram) |
| **Storage** | 238 GB NVMe SSD (203 GB available) |
| **CPU** | 6x ARM Cortex-A78AE @ 1.73 GHz |
| **GPU** | Ampere architecture, 918 MHz max |
| **Power** | ~5.7W typical |

## Software Environment

| Component | Version |
|-----------|---------|
| **JetPack** | 6.2.1 |
| **L4T** | R36.4.4 |
| **Linux Kernel** | 5.15.148-tegra |
| **Python** | 3.10.12 |
| **Node.js** | 24.11.1 |
| **NPM** | 11.6.2 |
| **Git** | 2.34.1 |

## NVIDIA Packages Status

### Installed
- nvidia-l4t-cuda (basic CUDA support)
- nvidia-l4t-core
- nvidia-l4t-camera
- nvidia-l4t-firmware

### Needs Installation
- **nvidia-tensorrt** (6.2.1+b38 available)
- **CUDA Toolkit** (full installation)
- **cuDNN** (for deep learning)
- **OpenCV** (with CUDA support)
- **PyTorch** (Jetson-optimized)
- **ONNX Runtime GPU**

## Python Packages Installed
- numpy 1.21.5
- Pillow 9.0.1

## Network Configuration

| Interface | Status | IP Address |
|-----------|--------|------------|
| wlP1p1s0 (WiFi) | UP | 192.168.0.245/24 |
| enP8p1s0 (Ethernet) | UP | 192.168.1.100/24 (for camera) |

## Camera Information

| Property | Value |
|----------|-------|
| **Model** | Hikvision DS-2CD7A47EWD-XZS |
| **IP Address** | 192.168.1.64 |
| **Firmware** | V5.7.21 (build 211130) |
| **Platform** | H8 |

### Streaming Channels

| Channel | Resolution | Bitrate | Use Case |
|---------|------------|---------|----------|
| 101 (Main) | 2560x1440 | 6 Mbps | Recording, high quality |
| 102 (Sub) | 704x576 | 1 Mbps | Low bandwidth processing |
| 103 (Third) | 1280x720 | 2 Mbps | **Recommended for AI processing** |

### Smart Features
- Motion Detection (VMD) - Available
- Audio Detection - Available
- Scene Change Detection - Available
- Defocus Detection - Available
- ROI (Region of Interest) - Available
- Face Detection - **Not available on camera** (we do this on Jetson)

## Memory Budget for Face Recognition

With 7.4 GB total RAM (shared CPU/GPU), budget allocation:

| Component | Estimated Memory |
|-----------|-----------------|
| OS + System | ~1.5 GB |
| SCRFD (2.5G model) | ~200 MB |
| ArcFace (MobileFaceNet) | ~100 MB |
| FAISS Index (1000 faces) | ~50 MB |
| Video Buffer (720p) | ~100 MB |
| FastAPI + React | ~300 MB |
| **Available Headroom** | ~5.2 GB |

## Recommended Model Configuration

### Face Detection: SCRFD_2.5G_KPS
- **Size**: 3.14 MB (ONNX)
- **Accuracy**: 93.80% (Easy), 92.02% (Medium), 77.13% (Hard)
- **Latency**: ~4.3ms (CPU reference)
- **Features**: 5-point keypoint detection for alignment
- **Rationale**: Best balance of accuracy and speed for 8GB device

### Face Recognition: MobileFaceNet (ArcFace)
- **Size**: ~4 MB
- **Accuracy**: 99.55% on LFW
- **Embedding**: 512-D vector
- **Rationale**:
  - ResNet50 (buffalo_l) requires ~400MB+ GPU memory
  - MobileFaceNet achieves comparable accuracy with 1/100th the size
  - Faster inference suitable for real-time processing

### Alternative: InsightFace buffalo_s
- Smaller than buffalo_l
- Same accuracy as buffalo_sc
- Good fallback if MobileFaceNet not available

## Installation Requirements

```bash
# TensorRT (for optimized inference)
sudo apt-get install nvidia-tensorrt

# Python ML stack
pip3 install onnxruntime-gpu  # Check Jetson-specific wheels
pip3 install opencv-python  # Or build with CUDA support
pip3 install insightface
pip3 install faiss-gpu  # Or faiss-cpu for initial testing

# Web framework
pip3 install fastapi uvicorn python-multipart

# Frontend
cd frontend && npm install
```

## Performance Expectations

With recommended configuration:
- **Stream Processing**: 15-25 FPS on 720p
- **Detection Latency**: ~30-50ms per frame
- **Recognition Latency**: <10ms per face (with FAISS)
- **GPU Utilization**: 40-60%
- **Memory Usage**: <4 GB typical
