#!/usr/bin/env python3
"""Test Dahua camera RTSP stream"""
import cv2
import sys

# Dahua RTSP URLs to try
urls = [
    "rtsp://admin:system123@10.1.1.68:554/cam/realmonitor?channel=1&subtype=0",
    "rtsp://admin:system123@10.1.1.68:554/cam/realmonitor?channel=1&subtype=1",
    "rtsp://admin:system123@10.1.1.68:554/live",
    "rtsp://admin:system123@10.1.1.68:554/h264/ch1/main/av_stream",
    "rtsp://admin:system123@10.1.1.68:554/h264/ch1/sub/av_stream",
]

print("Testing Dahua camera RTSP streams...\n")

for url in urls:
    print(f"Trying: {url[:50]}...")
    cap = cv2.VideoCapture(url)
    
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            h, w = frame.shape[:2]
            print(f"  ✓ SUCCESS! Resolution: {w}x{h}")
            cap.release()
            print(f"\nWorking URL: {url}")
            sys.exit(0)
        else:
            print(f"  ✗ Opened but no frames")
    else:
        print(f"  ✗ Failed to open")
    
    cap.release()

print("\nNo working stream found")
