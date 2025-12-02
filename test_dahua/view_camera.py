#!/usr/bin/env python3
"""
Dahua PTZ Camera Test Viewer
Controls: Q=quit, W/S/A/D=pan/tilt, Z/X=zoom, R=reset
"""
import cv2
import requests
from requests.auth import HTTPDigestAuth

CAMERA_IP = "10.1.1.68"
USERNAME = "admin"
PASSWORD = "system123"
RTSP_URL = f"rtsp://{USERNAME}:{PASSWORD}@{CAMERA_IP}:554/cam/realmonitor?channel=1&subtype=1"

auth = HTTPDigestAuth(USERNAME, PASSWORD)

def ptz_command(action, arg1=0, arg2=0, arg3=0):
    """Send PTZ command to camera"""
    url = f"http://{CAMERA_IP}/cgi-bin/ptz.cgi?action={action}&channel=0&code=Up&arg1={arg1}&arg2={arg2}&arg3={arg3}"
    try:
        requests.get(url, auth=auth, timeout=2)
    except:
        pass

def main():
    print("Opening Dahua camera stream...")
    print("Controls: Q=quit, W/S/A/D=pan/tilt, +/-=zoom")
    print("")
    
    cap = cv2.VideoCapture(RTSP_URL)
    
    if not cap.isOpened():
        print("Failed to open stream!")
        return
    
    print("Stream opened successfully!")
    print("Press Q to quit")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Frame read failed")
            break
        
        # Add info overlay
        cv2.putText(frame, f"Dahua PTZ @ {CAMERA_IP}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        cv2.imshow("Dahua Camera Test", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
