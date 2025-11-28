#!/bin/bash
# Script to run after OpenCV build completes
# This installs remaining dependencies and tests the system

set -e

echo "=== Setup Script for Face Recognition System ==="
echo "Run this after OpenCV build completes"
echo ""

# Check if OpenCV with CUDA is installed
echo "Step 1: Verifying OpenCV installation..."
python3 -c "
import cv2
print(f'OpenCV Version: {cv2.__version__}')
cuda_count = cv2.cuda.getCudaEnabledDeviceCount()
print(f'CUDA Devices: {cuda_count}')
if cuda_count == 0:
    print('ERROR: OpenCV CUDA not available!')
    exit(1)
print('OpenCV with CUDA verified!')
"

echo ""
echo "Step 2: Installing Python dependencies..."
pip3 install --upgrade pip

# Install ONNX Runtime
echo "Installing ONNX Runtime GPU..."
pip3 install onnxruntime-gpu || pip3 install onnxruntime

# Install InsightFace
echo "Installing InsightFace..."
pip3 install insightface

# Install FAISS
echo "Installing FAISS..."
pip3 install faiss-cpu

# Install web framework
echo "Installing FastAPI and dependencies..."
pip3 install -r /home/tempuser/Downloads/frs/backend/requirements.txt

echo ""
echo "Step 3: Testing camera connection..."
ping -c 1 192.168.1.64 || echo "Camera not reachable - check network"

# Test ISAPI
curl -s --digest -u admin:Mujeeb@321 "http://192.168.1.64/ISAPI/System/deviceInfo" > /dev/null && \
    echo "Camera ISAPI: OK" || echo "Camera ISAPI: FAILED"

echo ""
echo "Step 4: Downloading InsightFace models..."
python3 -c "
from insightface.app import FaceAnalysis
print('Downloading buffalo_s model...')
app = FaceAnalysis(name='buffalo_s', providers=['CPUExecutionProvider'])
app.prepare(ctx_id=-1, det_size=(640, 640))
print('Model download complete!')
"

echo ""
echo "Step 5: Creating data directories..."
mkdir -p /home/tempuser/Downloads/frs/data/{models,images,embeddings,snapshots}

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start the system:"
echo "  Backend:  cd /home/tempuser/Downloads/frs && python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"
echo "  Frontend: cd /home/tempuser/Downloads/frs/frontend && npm run dev"
echo ""
echo "Access at:"
echo "  Frontend: http://192.168.0.245:5173"
echo "  API Docs: http://192.168.0.245:8000/docs"
