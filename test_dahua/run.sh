#!/bin/bash
# Run Dahua Camera PTZ Control GUI (GStreamer + GTK)

cd "$(dirname "$0")"

# Set display if not set
export DISPLAY=${DISPLAY:-:0}

# Run the GUI
python3 dahua_camera_gui.py
