# Quick Start Guide - Face Recognition Security System

## TL;DR - Just Run It!

```bash
cd /home/tempuser/Downloads/frs
./start.sh
```

That's it! The system will start and show you the URLs.

---

## Scripts

| Script | Description |
|--------|-------------|
| `./start.sh` | Start backend + frontend + camera stream |
| `./stop.sh` | Stop everything |
| `./status.sh` | Check if running + system resources |

---

## Access URLs

After starting, access these URLs (replace IP with your Jetson IP):

| Service | URL |
|---------|-----|
| **Frontend (Main UI)** | http://192.168.0.245:5173 |
| **Backend API** | http://192.168.0.245:8000 |
| **API Documentation** | http://192.168.0.245:8000/docs |
| **Direct Video Stream** | http://192.168.0.245:8000/api/stream/mjpeg |

---

## First Time Setup

If this is your first time running, install dependencies:

```bash
# Install Python dependencies
pip3 install -r backend/requirements.txt

# Install GPU-accelerated ONNX Runtime (CRITICAL for performance!)
wget https://github.com/Shattered217/Jetson-Orin-Nano-Wheels/releases/download/onnxruntime-gpu-1.24.0/onnxruntime_gpu-1.24.0-cp310-cp310-linux_aarch64.whl
pip3 install onnxruntime_gpu-1.24.0-cp310-cp310-linux_aarch64.whl

# Install frontend dependencies
cd frontend && npm install && cd ..
```

---

## Camera Network Setup

The camera is on a separate network (192.168.1.x). If connection fails:

```bash
# Add IP address for camera network
sudo ip addr add 192.168.1.100/24 dev enP8p1s0

# Verify camera is reachable
ping 192.168.1.64
```

---

## Troubleshooting

### Backend won't start?
```bash
# Check logs
tail -f /tmp/frs_backend.log

# Common issues:
# - Port 8000 already in use: ./stop.sh first
# - Missing dependencies: pip3 install -r backend/requirements.txt
# - GPU not available: Check onnxruntime-gpu is installed
```

### Frontend won't start?
```bash
# Check logs
tail -f /tmp/frs_frontend.log

# Common issues:
# - Port 5173 in use: ./stop.sh first
# - Missing npm: sudo apt install nodejs npm
# - Missing modules: cd frontend && npm install
```

### No video stream?
```bash
# Check camera connection
ping 192.168.1.64

# Verify RTSP stream works
ffplay rtsp://admin:Mujeeb@321@192.168.1.64:554/Streaming/Channels/102

# Check if network is configured
ip addr show enP8p1s0 | grep 192.168.1
```

### Low FPS?
- Check Settings page for GPU usage
- Enable Motion Trigger (reduces idle GPU load)
- Reduce Frame Skip to 1-2

---

## UI Tabs

| Tab | Description |
|-----|-------------|
| **Dashboard** | Live video stream + alerts |
| **Persons** | Enroll/manage people |
| **Alerts** | View detection alerts |
| **Settings** | Adjust thresholds, view resources |

---

## Key Settings (Settings Tab)

| Setting | Default | Description |
|---------|---------|-------------|
| Detection Confidence | 0.5 | Min score to detect face (0.1-1.0) |
| Recognition Threshold | 0.4 | Similarity for match (0.1-1.0) |
| Frame Skip | 2 | Process every Nth frame |
| Motion Trigger | On | Only detect when movement |

---

## Useful Links

- **GitHub Repo**: https://github.com/mujeebawan/FRS_Jetson_nano_8gb
- **ONNX Runtime Wheels**: https://github.com/Shattered217/Jetson-Orin-Nano-Wheels
- **InsightFace Models**: https://github.com/deepinsight/insightface
- **Full Documentation**: See `docs/PROGRESS.md`

---

## Hardware Info

- **Device**: Jetson Orin Nano 8GB
- **JetPack**: 6.2.1 (R36.4.4)
- **Camera**: Hikvision DS-2CD7A47EWD-XZS
- **Performance**: 25-35 FPS with GPU acceleration

---

## Quick Commands

```bash
# Start everything
./start.sh

# Stop everything
./stop.sh

# Check status
./status.sh

# View backend logs
tail -f /tmp/frs_backend.log

# View frontend logs
tail -f /tmp/frs_frontend.log

# Monitor GPU
tegrastats

# Test camera stream
curl http://localhost:8000/api/stream/status

# API health check
curl http://localhost:8000/api/health

# Switch model
curl -X POST "http://localhost:8000/api/system/models/change?model=buffalo_l"
```

---

## Systemd Service

The system auto-starts on boot:

```bash
# Check status
sudo systemctl status frs

# Restart
sudo systemctl restart frs

# View logs
journalctl -u frs -f
```
