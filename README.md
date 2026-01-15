# Face Recognition Security System - Base System V2

Real-time face detection and recognition system for **security monitoring**, optimized for **Jetson Orin Nano 8GB**.

## Key Features

- **JWT Authentication** - Secure login with access/refresh tokens
- **Multi-Camera Support** - Up to 4 cameras with DeepStream tiled view
- **DeepStream Pipeline** - Hardware-accelerated H264 decoding
- **TensorRT Acceleration** - SCRFD detection (~20ms) + ArcFace recognition (~8ms)
- **FAISS GPU Matching** - Fast face similarity search
- **Real-time Alerts** - WebSocket notifications with snapshots
- **Watchlist System** - Criminal, suspect, VIP, banned person categories

## Hardware Requirements

| Component | Specification |
|-----------|---------------|
| **Device** | NVIDIA Jetson Orin Nano 8GB |
| **JetPack** | 6.x (with DeepStream 7.x) |
| **Cameras** | Dahua/Hikvision IP cameras (RTSP) |
| **Network** | Gigabit Ethernet |

## Quick Start

```bash
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

**Default Login:**
- Username: `admin`
- Password: `admin123`

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │Dashboard│ │ Persons │ │ Alerts  │ │ Cameras │ │Settings │   │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │
│       └───────────┴───────────┴───────────┴───────────┘         │
│                              │ JWT Auth                          │
└──────────────────────────────┼──────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────┐
│                     Backend (FastAPI)                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    API Routes                            │    │
│  │  /auth  /stream  /persons  /alerts  /cameras  /system   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│  ┌───────────────────────────┴───────────────────────────────┐  │
│  │              DeepStream Pipeline                           │  │
│  │  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   │  │
│  │  │ RTSP    │──▶│ H264    │──▶│ Tiler   │──▶│ MJPEG   │   │  │
│  │  │ Sources │   │ Decode  │   │ (NxM)   │   │ Output  │   │  │
│  │  └─────────┘   └─────────┘   └─────────┘   └─────────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────┴───────────────────────────────┐  │
│  │              TensorRT Process (Separate)                   │  │
│  │  ┌─────────────────┐      ┌─────────────────────────────┐ │  │
│  │  │ SCRFD Detection │──▶   │ ArcFace Recognition (batch) │ │  │
│  │  │ det_10g_fp16    │      │ w600k_r50_batch32_fp16      │ │  │
│  │  └─────────────────┘      └─────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────┴───────────────────────────────┐  │
│  │                    FAISS GPU Index                         │  │
│  │              Face embedding similarity search              │  │
│  └───────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Authentication

The system uses JWT (JSON Web Tokens) for authentication:

- **Access Token**: 30 minutes validity
- **Refresh Token**: 7 days validity
- All API endpoints require authentication (except `/health`)
- MJPEG stream endpoints are public (browser can't send auth headers for `<img>` tags)

### User Roles

| Role | Permissions |
|------|-------------|
| **admin** | Full access - manage users, cameras, settings |
| **user** | View-only - dashboard, alerts, persons |

## API Endpoints

### Authentication
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Login, returns tokens |
| `/api/auth/logout` | POST | Logout |
| `/api/auth/refresh` | POST | Refresh access token |
| `/api/auth/me` | GET | Get current user |

### Stream
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/stream/start` | GET | Admin | Start DeepStream pipeline |
| `/api/stream/stop` | GET | Admin | Stop pipeline |
| `/api/stream/status` | GET | User | Get FPS and status |
| `/api/stream/mjpeg` | GET | Public | Tiled MJPEG feed (all cameras) |
| `/api/stream/mjpeg/camera/{id}` | GET | Public | Single camera MJPEG |

### Persons
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/persons/` | GET | User | List enrolled persons |
| `/api/persons/enroll` | POST | Admin | Enroll new person |
| `/api/persons/enroll-from-camera` | POST | Admin | Enroll from live camera |
| `/api/persons/{id}/image` | GET | User | Get reference image |
| `/api/persons/{id}` | DELETE | Admin | Delete person |

### Alerts
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/alerts/` | GET | User | List alerts with filters |
| `/api/alerts/{id}/acknowledge` | POST | User | Acknowledge alert |
| `/api/alerts/{id}/snapshot` | GET | User | Get captured image |
| `/api/alerts/ws` | WS | User | Real-time WebSocket |

### Cameras
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/cameras/` | GET | User | List cameras |
| `/api/cameras/` | POST | Admin | Add camera |
| `/api/cameras/{id}` | PUT | Admin | Update camera |
| `/api/cameras/{id}` | DELETE | Admin | Delete camera |

### System
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/system/status` | GET | User | System status |
| `/api/system/resources` | GET | User | CPU, GPU, RAM, temp |
| `/api/system/settings` | GET | User | Current settings |
| `/api/system/settings/update` | POST | Admin | Update settings |

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Detection Confidence | 0.5 | Minimum face detection score |
| Recognition Threshold | 0.38 | Similarity threshold for match |
| Frame Skip | 2 | Process every Nth frame |
| Alert Cooldown | 60s | Seconds between alerts for same person |
| Alert on Unknown | true | Generate alerts for unknown faces |
| Alert on Known | true | Generate alerts for known faces |
| Video Recording | false | Record video clips on alerts |

## Watchlist Status

| Status | Threat Level | Description |
|--------|--------------|-------------|
| `criminal` | critical/high | Known criminal - alert authorities |
| `most_wanted` | critical | Most wanted - immediate action |
| `suspect` | medium | Suspect - monitor closely |
| `person_of_interest` | low | Person of interest - log sighting |
| `banned` | medium | Banned from premises |
| `vip` | - | VIP - premium service |
| `normal` | - | Normal enrolled person |

## Project Structure

```
Frs_sec/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/        # auth, stream, persons, alerts, cameras, system
│   │   │   └── deps.py        # Authentication dependencies
│   │   ├── core/
│   │   │   ├── security.py    # JWT token handling
│   │   │   ├── recognizer.py  # FAISS face matching
│   │   │   └── trt_inference.py # TensorRT inference
│   │   ├── models/
│   │   │   └── database.py    # SQLAlchemy models
│   │   ├── services/
│   │   │   ├── deepstream_stream.py  # DeepStream pipeline
│   │   │   ├── trt_process.py        # TRT worker process
│   │   │   └── alerts.py             # Alert management
│   │   ├── config.py
│   │   └── main.py
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/        # LiveStream, PersonList, AlertList, etc.
│       ├── contexts/          # AuthContext
│       ├── services/api.ts    # API client with auth
│       └── App.tsx            # Main app with login gate
├── data/
│   ├── persons/               # Enrolled person images
│   ├── embeddings/            # FAISS embedding files
│   ├── alerts/                # Alert snapshots (date-wise)
│   ├── tensorrt_engines/      # TensorRT engine files
│   ├── settings.json          # Runtime settings
│   └── frs.db                 # SQLite database
├── configs/deepstream/        # DeepStream config files
├── start.sh                   # Start backend + frontend
├── stop.sh                    # Stop all services
└── status.sh                  # System status check
```

## Performance

| Metric | Value |
|--------|-------|
| Detection (SCRFD) | ~20ms |
| Recognition (ArcFace) | ~8ms per face |
| FAISS Matching | ~1-5ms |
| Total Pipeline | ~30-50ms per frame |
| Stream FPS | 20-25 FPS |
| GPU Memory | ~4-5GB |

## Troubleshooting

### Backend won't start
```bash
# Check logs
tail -f /tmp/frs_backend.log

# Kill orphan processes
pkill -f "multiprocessing.spawn"
```

### GPU out of memory
```bash
# Free memory by killing orphan TRT processes
pkill -f "multiprocessing.spawn"

# Check memory
free -h
```

### Login issues
- Default credentials: `admin` / `admin123`
- Clear browser localStorage if token issues
- Check backend logs for auth errors

## License

MIT License

## Acknowledgments

- [NVIDIA DeepStream](https://developer.nvidia.com/deepstream-sdk) - Video analytics SDK
- [InsightFace](https://github.com/deepinsight/insightface) - SCRFD + ArcFace models
- [FAISS](https://github.com/facebookresearch/faiss) - Similarity search
- [FastAPI](https://fastapi.tiangolo.com/) - Backend framework
- [React](https://react.dev/) + [Vite](https://vitejs.dev/) - Frontend
