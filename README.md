# Face Recognition Security System

Real-time face detection and recognition system optimized for **Jetson Orin Nano 8GB**.

## Features

- **Real-time Face Detection** using SCRFD (InsightFace)
- **Face Recognition** with ArcFace embeddings and FAISS similarity search
- **Hikvision Camera Integration** via ISAPI and RTSP
- **Motion-triggered Processing** to reduce computational load
- **React Frontend** with live stream viewer, person enrollment, and alerts
- **FastAPI Backend** with WebSocket support for real-time updates

## Hardware Requirements

| Component | Specification |
|-----------|---------------|
| **Device** | NVIDIA Jetson Orin Nano 8GB |
| **Camera** | Hikvision DS-2CD7A47EWD-XZS (or compatible) |
| **JetPack** | 6.2+ |
| **Storage** | 32GB+ recommended |

## Quick Start

### 1. Install Dependencies

```bash
# Clone the repository
git clone https://github.com/mujeebawan/FRS_Jetson_nano_8gb.git
cd FRS_Jetson_nano_8gb

# Install NVIDIA packages (if not already installed)
sudo apt update
sudo apt install -y nvidia-tensorrt nvidia-cuda

# Install Python dependencies
pip3 install -r backend/requirements.txt

# Install frontend dependencies
cd frontend && npm install
```

### 2. Configure Network

The camera must be accessible from the Jetson. Add the camera network:

```bash
# Add IP to ethernet interface for camera network
sudo ip addr add 192.168.1.100/24 dev enP8p1s0

# Verify camera is reachable
ping 192.168.1.64
```

### 3. Start the System

```bash
# Start backend
cd /path/to/frs
python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# Start frontend (in another terminal)
cd frontend
npm run dev
```

### 4. Access the Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Project Structure

```
frs/
├── backend/
│   ├── app/
│   │   ├── api/routes/     # API endpoints
│   │   ├── core/           # Face detection & recognition
│   │   ├── services/       # Camera & stream services
│   │   ├── config.py       # Configuration
│   │   └── main.py         # FastAPI application
│   └── requirements.txt
├── frontend/               # React + Vite + TypeScript
│   ├── src/
│   │   ├── components/     # UI components
│   │   └── services/       # API client
│   └── package.json
├── data/                   # Runtime data
│   ├── embeddings/         # Face embeddings
│   ├── images/             # Enrolled face images
│   └── snapshots/          # Alert snapshots
├── docs/                   # Documentation
└── scripts/                # Setup scripts
```

## Configuration

Create a `.env` file in the project root:

```env
# Camera
CAMERA_IP=192.168.1.64
CAMERA_USERNAME=admin
CAMERA_PASSWORD=your_password

# Recognition
DETECTION_CONFIDENCE=0.5
RECOGNITION_THRESHOLD=0.4
FRAME_SKIP=2

# Security
SECRET_KEY=your-secret-key
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/stream/start` | POST | Start video stream |
| `/api/stream/stop` | POST | Stop video stream |
| `/api/stream/mjpeg` | GET | MJPEG video feed |
| `/api/persons/enroll` | POST | Enroll new person |
| `/api/persons/` | GET | List enrolled persons |
| `/api/alerts/` | GET | Get recent alerts |
| `/api/system/status` | GET | System status |

## Models Used

- **Detection**: SCRFD 2.5G KPS (InsightFace buffalo_s)
- **Recognition**: MobileFaceNet / ArcFace (512-D embeddings)
- **Similarity Search**: FAISS (CPU)

## Performance

On Jetson Orin Nano 8GB with 720p stream:

| Metric | Value |
|--------|-------|
| Detection Latency | ~50-60ms |
| Recognition Latency | <10ms |
| FPS (processing) | 15-20 |
| Memory Usage | ~3-4GB |

## Building OpenCV with CUDA

The system requires OpenCV built with CUDA support. See `docs/SETUP_GUIDE.md` for detailed build instructions.

```bash
# Quick reference (after building)
python3 -c "import cv2; print(cv2.__version__); print(cv2.cuda.getCudaEnabledDeviceCount())"
# Expected: OpenCV 4.10.0, CUDA: 1
```

## License

MIT License

## Acknowledgments

- [InsightFace](https://github.com/deepinsight/insightface) - Face detection and recognition
- [FAISS](https://github.com/facebookresearch/faiss) - Similarity search
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [React](https://react.dev/) - Frontend framework
