#!/bin/bash
# Open Dahua camera web interface

CAMERA_IP="10.1.1.68"

echo "Opening Dahua camera web interface..."
echo "URL: http://$CAMERA_IP"
echo ""
echo "Login credentials:"
echo "  Username: admin"
echo "  Password: system123p"
echo ""

# Try different browsers
if command -v firefox &> /dev/null; then
    firefox "http://$CAMERA_IP" &
elif command -v chromium-browser &> /dev/null; then
    chromium-browser "http://$CAMERA_IP" &
elif command -v google-chrome &> /dev/null; then
    google-chrome "http://$CAMERA_IP" &
else
    xdg-open "http://$CAMERA_IP" &
fi

echo "Browser opened. Use the web interface for PTZ controls."
