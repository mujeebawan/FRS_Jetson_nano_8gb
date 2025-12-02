# Face Recognition Security System

Real-time face detection and recognition system for **security monitoring**, optimized for **Jetson Orin Nano 8GB**.

## Features

- **Real-time Face Detection** - SCRFD models with GPU acceleration (25-35 FPS)
- **Face Recognition** - ArcFace 512-D embeddings with FAISS similarity search
- **Multi-Model Support** - Switch between buffalo_s (fast) and buffalo_l (accurate) at runtime
- **FP16 Optimization** - Half-precision models for faster inference on Jetson
- **Motion Trigger** - Optional motion-based processing to reduce GPU load
- **Hikvision Integration** - ISAPI for camera control and motion detection
- **Alert Management** - Real-time WebSocket alerts with cooldown
- **Systemd Service** - Auto-start on boot

## Hardware

| Component | Specification |
|-----------|---------------|
| **Device** | NVIDIA Jetson Orin Nano 8GB |
| **JetPack** | 6.2.1 (R36.4.4) |
| **Camera** | Hikvision DS-2CD7A47EWD-XZS |
| **Network** | Gigabit Ethernet (192.168.1.x) |

## Quick Start

```bash
# Clone and enter directory
cd /home/tempuser/Downloads/frs

# Start the system
./start.sh

# Check status
./status.sh

# Stop the system
./stop.sh
```

**Access URLs:**
- Frontend: http://192.168.0.245:5173
- Backend API: http://192.168.0.245:8000
- API Docs: http://192.168.0.245:8000/docs
- MJPEG Stream: http://192.168.0.245:8000/api/stream/mjpeg

## Model Packs

| Model | Detection | Recognition | Size (FP16) | FPS | Use Case |
|-------|-----------|-------------|-------------|-----|----------|
| **buffalo_s** | SCRFD det_500m | W600K-MBF (MobileFaceNet) | 88MB | 25-35 | Real-time, lower memory |
| **buffalo_l** | SCRFD det_10g | W600K-R50 (ResNet50) | 171MB | 15-20 | Higher accuracy |

Switch models from Settings tab or via API:
```bash
curl -X POST "http://localhost:8000/api/system/models/change?model=buffalo_l&use_fp16=true"
```

## Multi-Model Enrollment

- **Enroll once, works on all models**: When you enroll a person, embeddings are generated for all available models automatically.
- **Delete once, removed everywhere**: When you delete a person, they are removed from all model embedding files.
- **Auto-regeneration**: When switching to a model with no embeddings, the system auto-regenerates from saved images.

## Project Structure

```
frs/
├── backend/
│   ├── app/
│   │   ├── api/routes/      # stream, persons, alerts, system
│   │   ├── core/            # detector.py, recognizer.py
│   │   ├── models/          # database.py (SQLAlchemy)
│   │   ├── services/        # camera, stream, alerts, enrollment
│   │   ├── config.py
│   │   └── main.py
│   └── requirements.txt
├── frontend/                 # React + Vite + TypeScript
│   └── src/
│       ├── components/      # LiveStream, PersonList, AlertList, SystemSettings
│       └── services/api.ts
├── data/
│   ├── persons/             # Enrolled person images
│   ├── embeddings/          # Model-specific embedding files
│   ├── snapshots/           # Alert snapshots (date-wise)
│   └── frs.db               # SQLite database
├── scripts/
│   └── convert_fp16.py      # FP16 model conversion
├── docs/
│   └── PROGRESS.md          # Development progress
├── start.sh                 # Start backend + frontend
├── stop.sh                  # Stop all services
├── status.sh                # System status check
├── frs.service              # Systemd service file
├── QUICKSTART.md            # Quick reference guide
└── README.md                # This file
```

## API Endpoints

### Stream
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stream/start` | GET | Start video stream |
| `/api/stream/stop` | GET | Stop video stream |
| `/api/stream/status` | GET | Stream FPS and status |
| `/api/stream/mjpeg` | GET | MJPEG video feed |
| `/api/stream/ws` | WS | WebSocket video stream |

### Persons
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/persons/` | GET | List all enrolled persons |
| `/api/persons/enroll` | POST | Enroll new person |
| `/api/persons/{id}` | GET | Get person details |
| `/api/persons/{id}` | DELETE | Delete person |

### Alerts
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/alerts/` | GET | List recent alerts |
| `/api/alerts/ws` | WS | Real-time alert WebSocket |

### System
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/system/status` | GET | System status |
| `/api/system/resources` | GET | CPU, GPU, RAM, temp |
| `/api/system/settings` | GET | Current settings |
| `/api/system/settings/update` | POST | Update settings |
| `/api/system/models` | GET | Available models |
| `/api/system/models/change` | POST | Switch model |

## Settings

| Setting | Range | Default | Description |
|---------|-------|---------|-------------|
| Detection Confidence | 0.1-1.0 | 0.5 | Minimum face detection score |
| Recognition Threshold | 0.1-1.0 | 0.4 | Similarity for match |
| Frame Skip | 1-10 | 2 | Process every Nth frame |
| Motion Trigger | on/off | off | Only detect on motion |
| Alert Cooldown | 1-300s | 10 | Seconds between alerts |

## Systemd Service

The system auto-starts on boot:

```bash
# Check service status
sudo systemctl status frs

# Start/stop/restart
sudo systemctl start frs
sudo systemctl stop frs
sudo systemctl restart frs

# View logs
journalctl -u frs -f
```

## GPU Setup for JetPack 6.x

JetPack 6.x uses cuDNN 9.x. Install compatible ONNX Runtime:

```bash
wget https://github.com/Shattered217/Jetson-Orin-Nano-Wheels/releases/download/onnxruntime-gpu-1.24.0/onnxruntime_gpu-1.24.0-cp310-cp310-linux_aarch64.whl
pip3 install onnxruntime_gpu-1.24.0-cp310-cp310-linux_aarch64.whl
```

## FP16 Model Conversion

Convert models to FP16 for faster inference:

```bash
pip3 install onnxconverter-common
python3 scripts/convert_fp16.py
```

This creates `~/.insightface/models/buffalo_s_fp16/` and `buffalo_l_fp16/`.

## Performance

| Configuration | FPS | GPU Usage |
|--------------|-----|-----------|
| CPU only | 1-2 | 0% |
| GPU (FP32) | 15-20 | 60-80% |
| GPU (FP16) buffalo_s | 25-35 | 45-70% |
| GPU (FP16) buffalo_l | 15-20 | 60-85% |
| With Motion Trigger | 30-40 | 20-50% |

## Troubleshooting

### Backend won't start
```bash
tail -f /tmp/frs_backend.log
```

### Camera not connecting
```bash
# Verify camera network
ping 192.168.1.64

# Add IP if missing
sudo ip addr add 192.168.1.100/24 dev enP8p1s0
```

### Low FPS
- Check GPU usage in Settings tab
- Enable Motion Trigger
- Use buffalo_s model for higher FPS

## License

MIT License

## Acknowledgments

- [InsightFace](https://github.com/deepinsight/insightface) - SCRFD + ArcFace
- [FAISS](https://github.com/facebookresearch/faiss) - Similarity search
- [Jetson-Orin-Nano-Wheels](https://github.com/Shattered217/Jetson-Orin-Nano-Wheels) - ONNX Runtime wheels
- [FastAPI](https://fastapi.tiangolo.com/) - Backend framework
- [React](https://react.dev/) + [Vite](https://vitejs.dev/) - Frontend
