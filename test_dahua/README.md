# Dahua Camera Control Panel

GTK-based GUI for Dahua IP cameras with live RTSP stream and embedded PTZ controls.

## Features

- Live RTSP video stream (80% of screen)
- Embedded PTZ controls from camera web interface (auto-login)
- Dark theme UI
- Fixed layout optimized for control room use

## Camera Credentials

```
IP Address: 10.1.1.68
Username:   admin
Password:   system123
RTSP Port:  554
Channel:    1
Subtype:    1 (sub-stream)
```

## RTSP URL Format

```
rtsp://admin:system123@10.1.1.68:554/cam/realmonitor?channel=1&subtype=1
```

- `subtype=0` - Main stream (1080p, higher bandwidth)
- `subtype=1` - Sub stream (lower resolution, faster)

## Requirements

Install dependencies on Jetson/Ubuntu:

```bash
sudo apt update
sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.0 python3-opencv python3-numpy
```

## Usage

```bash
# Make executable
chmod +x run.sh dahua_camera_gui.py

# Run
./run.sh
# or
python3 dahua_camera_gui.py
```

## Configuration

Edit `dahua_camera_gui.py` to change camera settings:

```python
DEFAULT_CAMERA_IP = "10.1.1.68"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "system123"
DEFAULT_RTSP_PORT = "554"
DEFAULT_CHANNEL = "1"
DEFAULT_SUBTYPE = "1"
```

## Layout

```
+----------------------------------+-------+
|                                  |  PTZ  |
|                                  |  11%  |
|           STREAM (80%)           +-------+
|                                  |       |
|                                  |  9%   |
+----------------------------------+-------+
```

## Tested On

- NVIDIA Jetson Orin Nano (JetPack 5.x)
- Ubuntu 20.04/22.04
