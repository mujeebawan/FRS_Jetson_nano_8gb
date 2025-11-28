# Setup Guide - Jetson Orin Nano 8GB

Complete step-by-step setup guide for the Face Recognition Security System.

## Table of Contents
1. [Prerequisites Check](#1-prerequisites-check)
2. [Install NVIDIA Packages](#2-install-nvidia-packages)
3. [Build OpenCV with CUDA](#3-build-opencv-with-cuda)
4. [Install Python Dependencies](#4-install-python-dependencies)
5. [Install Face Recognition Models](#5-install-face-recognition-models)
6. [Setup Frontend](#6-setup-frontend)
7. [Configure Network](#7-configure-network)
8. [Run Application](#8-run-application)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Prerequisites Check

### Verify JetPack Version
```bash
cat /etc/nv_tegra_release
# Expected: R36 (JetPack 6.x)

dpkg -l | grep nvidia-jetpack
# Should show nvidia-jetpack 6.2.x
```

### Check Available Memory
```bash
free -h
# Should show ~7.4 GB total RAM
```

### Check Storage
```bash
df -h /
# Need at least 20GB free for builds
```

---

## 2. Install NVIDIA Packages

### Step 2.1: Update Package List
```bash
sudo apt update
```

### Step 2.2: Install TensorRT
```bash
sudo apt install -y nvidia-tensorrt
```

### Step 2.3: Install CUDA Development Tools
```bash
sudo apt install -y nvidia-cuda nvidia-cuda-dev
```

### Step 2.4: Install cuDNN
```bash
sudo apt install -y nvidia-cudnn8-dev
```

### Step 2.5: Verify CUDA
```bash
nvcc --version
# Should show CUDA 12.x
```

### Step 2.6: Set Environment Variables
Add to `~/.bashrc`:
```bash
echo 'export PATH=/usr/local/cuda/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

---

## 3. Build OpenCV with CUDA

**IMPORTANT**: The pip version of OpenCV does NOT include CUDA support. We must build from source.

### Step 3.1: Install Build Dependencies
```bash
sudo apt install -y \
    build-essential cmake git pkg-config \
    libjpeg-dev libtiff-dev libpng-dev \
    libavcodec-dev libavformat-dev libswscale-dev \
    libv4l-dev libxvidcore-dev libx264-dev \
    libgtk-3-dev libatlas-base-dev gfortran \
    python3-dev python3-numpy \
    libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-bad1.0-dev gstreamer1.0-plugins-ugly \
    gstreamer1.0-tools gstreamer1.0-gl
```

### Step 3.2: Clone OpenCV Source
```bash
cd ~
git clone --depth 1 --branch 4.10.0 https://github.com/opencv/opencv.git
git clone --depth 1 --branch 4.10.0 https://github.com/opencv/opencv_contrib.git
```

### Step 3.3: Create Build Directory
```bash
cd ~/opencv
mkdir build && cd build
```

### Step 3.4: Configure with CMake
**CRITICAL**: This configuration enables CUDA support for Jetson Orin Nano

```bash
cmake \
    -D CMAKE_BUILD_TYPE=RELEASE \
    -D CMAKE_INSTALL_PREFIX=/usr/local \
    -D OPENCV_EXTRA_MODULES_PATH=~/opencv_contrib/modules \
    -D EIGEN_INCLUDE_PATH=/usr/include/eigen3 \
    -D WITH_CUDA=ON \
    -D CUDA_ARCH_BIN="8.7" \
    -D CUDA_ARCH_PTX="" \
    -D WITH_CUDNN=ON \
    -D OPENCV_DNN_CUDA=ON \
    -D ENABLE_FAST_MATH=ON \
    -D CUDA_FAST_MATH=ON \
    -D WITH_CUBLAS=ON \
    -D WITH_GSTREAMER=ON \
    -D WITH_V4L=ON \
    -D WITH_LIBV4L=ON \
    -D WITH_OPENGL=ON \
    -D WITH_FFMPEG=ON \
    -D BUILD_opencv_python3=ON \
    -D PYTHON3_EXECUTABLE=$(which python3) \
    -D PYTHON3_INCLUDE_DIR=$(python3 -c "from distutils.sysconfig import get_python_inc; print(get_python_inc())") \
    -D PYTHON3_PACKAGES_PATH=$(python3 -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())") \
    -D OPENCV_GENERATE_PKGCONFIG=ON \
    -D BUILD_EXAMPLES=OFF \
    -D BUILD_TESTS=OFF \
    -D BUILD_PERF_TESTS=OFF \
    -D BUILD_DOCS=OFF \
    ..
```

**Note**: `CUDA_ARCH_BIN="8.7"` is specific to Jetson Orin Nano (Ampere architecture).

### Step 3.5: Verify CUDA is Enabled
Check CMake output for:
```
--   NVIDIA CUDA:                   YES (ver 12.x, CUFFT CUBLAS)
--     NVIDIA GPU arch:             87
--   cuDNN:                         YES (ver 8.x)
```

### Step 3.6: Build OpenCV
```bash
# Use 4 cores to avoid memory issues
make -j4
```
**Expected time**: 2-4 hours on Jetson Orin Nano

### Step 3.7: Install OpenCV
```bash
sudo make install
sudo ldconfig
```

### Step 3.8: Verify Installation
```bash
python3 -c "import cv2; print(f'OpenCV: {cv2.__version__}'); print(f'CUDA: {cv2.cuda.getCudaEnabledDeviceCount()}')"
```
Expected output:
```
OpenCV: 4.10.0
CUDA: 1
```

---

## 4. Install Python Dependencies

### Step 4.1: Create Virtual Environment (Optional but Recommended)
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 4.2: Upgrade pip
```bash
pip3 install --upgrade pip wheel setuptools
```

### Step 4.3: Install ONNX Runtime for Jetson
```bash
# Get Jetson-specific wheel from NVIDIA
pip3 install onnxruntime-gpu
```

If not available, check: https://elinux.org/Jetson_Zoo#ONNX_Runtime

### Step 4.4: Install InsightFace
```bash
pip3 install insightface
```

### Step 4.5: Install FAISS
```bash
# CPU version (simpler, still fast for <10K faces)
pip3 install faiss-cpu

# OR GPU version (requires more setup)
# pip3 install faiss-gpu
```

### Step 4.6: Install Web Framework
```bash
pip3 install fastapi uvicorn[standard] python-multipart pydantic pydantic-settings
```

### Step 4.7: Install Remaining Dependencies
```bash
cd /home/tempuser/Downloads/frs
pip3 install -r backend/requirements.txt
```

---

## 5. Install Face Recognition Models

### Step 5.1: Download Models (Automatic)
InsightFace downloads models automatically on first use:
```python
python3 -c "
from insightface.app import FaceAnalysis
app = FaceAnalysis(name='buffalo_s', providers=['CPUExecutionProvider'])
app.prepare(ctx_id=-1, det_size=(640, 640))
print('Models downloaded successfully')
"
```

### Step 5.2: Verify Models Location
```bash
ls ~/.insightface/models/
# Should show: buffalo_s/
```

---

## 6. Setup Frontend

### Step 6.1: Install Node.js (if needed)
Already installed: Node.js 24.11.1

### Step 6.2: Install Frontend Dependencies
```bash
cd /home/tempuser/Downloads/frs/frontend
npm install
```

### Step 6.3: Build for Production
```bash
npm run build
```

---

## 7. Configure Network

### Step 7.1: Camera Network
The camera is on 192.168.1.64. Your Jetson needs access:

```bash
# Add IP to ethernet interface
sudo ip addr add 192.168.1.100/24 dev enP8p1s0

# Make persistent (add to /etc/network/interfaces or use NetworkManager)
```

### Step 7.2: Verify Camera Connection
```bash
ping -c 2 192.168.1.64
# Should get responses
```

### Step 7.3: Test Camera ISAPI
```bash
curl --digest -u admin:Mujeeb@321 "http://192.168.1.64/ISAPI/System/deviceInfo"
# Should return XML with camera info
```

---

## 8. Run Application

### Step 8.1: Set Environment Variables
Create `.env` file:
```bash
cat > /home/tempuser/Downloads/frs/.env << 'EOF'
CAMERA_IP=192.168.1.64
CAMERA_USERNAME=admin
CAMERA_PASSWORD=Mujeeb@321
SECRET_KEY=your-secure-random-key-here
DEBUG=true
EOF
```

### Step 8.2: Start Backend
```bash
cd /home/tempuser/Downloads/frs
python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

### Step 8.3: Start Frontend (Development)
```bash
cd /home/tempuser/Downloads/frs/frontend
npm run dev
```

### Step 8.4: Access Application
- **Frontend**: http://192.168.0.245:5173
- **Backend API**: http://192.168.0.245:8000
- **API Docs**: http://192.168.0.245:8000/docs

---

## 9. Troubleshooting

### OpenCV CUDA Not Working
```bash
# Check CUDA devices
python3 -c "import cv2; print(cv2.cuda.getCudaEnabledDeviceCount())"
# If 0, rebuild OpenCV with correct CUDA_ARCH_BIN
```

### RTSP Stream Fails
```bash
# Test with ffplay
ffplay -rtsp_transport tcp "rtsp://admin:Mujeeb@321@192.168.1.64:554/Streaming/Channels/103"
```

### InsightFace Model Download Fails
```bash
# Manual download
mkdir -p ~/.insightface/models
cd ~/.insightface/models
# Download from https://github.com/deepinsight/insightface/releases
```

### Out of Memory
```bash
# Enable swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Add to /etc/fstab for persistence
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### FAISS GPU Issues
Start with CPU version (`faiss-cpu`) which is sufficient for <10,000 faces.

---

## Quick Reference

| Service | URL |
|---------|-----|
| Frontend | http://192.168.0.245:5173 |
| Backend API | http://192.168.0.245:8000 |
| API Docs | http://192.168.0.245:8000/docs |
| Stream | http://192.168.0.245:8000/api/stream/mjpeg |
| Camera | 192.168.1.64 |

## Next Steps
1. Test camera stream: `/api/stream/start`
2. Enroll faces: `/api/persons/enroll`
3. Configure alerts: Settings page
4. Monitor: Dashboard
