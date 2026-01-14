#!/bin/bash
#
# Face Recognition Security System - Status Script
# Shows system status and resource usage
#

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BACKEND_PORT=8000
FRONTEND_PORT=5173
JETSON_IP=$(hostname -I | awk '{print $1}')

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Face Recognition System Status${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check Backend
echo -e "${YELLOW}Backend (Port $BACKEND_PORT):${NC}"
if curl -s "http://localhost:$BACKEND_PORT/health" > /dev/null 2>&1; then
    BACKEND_PID=$(lsof -t -i :$BACKEND_PORT 2>/dev/null | head -1)
    echo -e "  Status: ${GREEN}Running${NC} (PID: $BACKEND_PID)"

    # Get stream status (includes pipeline info)
    STREAM_STATUS=$(curl -s "http://localhost:$BACKEND_PORT/api/stream/status" 2>/dev/null)
    if [ -n "$STREAM_STATUS" ]; then
        FPS=$(echo "$STREAM_STATUS" | grep -o '"fps":[0-9.]*' | cut -d: -f2)
        NUM_CAMS=$(echo "$STREAM_STATUS" | grep -o '"num_cameras":[0-9]*' | cut -d: -f2)
        PIPELINE=$(echo "$STREAM_STATUS" | grep -o '"pipeline":"[^"]*"' | cut -d'"' -f4)
        RUNNING=$(echo "$STREAM_STATUS" | grep -o '"running":true' | wc -l)
        if [ "$RUNNING" -gt 0 ]; then
            echo -e "  Stream: ${GREEN}Active${NC} at ${FPS} FPS"
            echo -e "  Cameras: ${NUM_CAMS}"
            echo -e "  Pipeline: ${PIPELINE}"
        else
            echo -e "  Stream: ${YELLOW}Stopped${NC}"
        fi
    fi
else
    echo -e "  Status: ${RED}Stopped${NC}"
fi

# Check Frontend
echo ""
echo -e "${YELLOW}Frontend (Port $FRONTEND_PORT):${NC}"
if curl -s "http://localhost:$FRONTEND_PORT" > /dev/null 2>&1; then
    FRONTEND_PID=$(lsof -t -i :$FRONTEND_PORT 2>/dev/null | head -1)
    echo -e "  Status: ${GREEN}Running${NC} (PID: $FRONTEND_PID)"
else
    echo -e "  Status: ${RED}Stopped${NC}"
fi

# Check Cameras (from API)
echo ""
echo -e "${YELLOW}Cameras:${NC}"
CAMERAS=$(curl -s "http://localhost:$BACKEND_PORT/api/cameras/" 2>/dev/null)
if [ -n "$CAMERAS" ] && [ "$CAMERAS" != "[]" ]; then
    # Check each camera's connectivity
    for ip in $(echo "$CAMERAS" | python3 -c "import sys,json; print(' '.join([c['ip_address'] for c in json.load(sys.stdin)]))" 2>/dev/null); do
        CAM_NAME=$(echo "$CAMERAS" | python3 -c "import sys,json; cams=json.load(sys.stdin); print(next((c['name'] for c in cams if c['ip_address']=='$ip'),'Camera'))" 2>/dev/null)
        if ping -c 1 -W 1 $ip > /dev/null 2>&1; then
            echo -e "  ${CAM_NAME} (${ip}): ${GREEN}Reachable${NC}"
        else
            echo -e "  ${CAM_NAME} (${ip}): ${RED}Not reachable${NC}"
        fi
    done
else
    echo -e "  ${YELLOW}No cameras configured${NC}"
fi

# System Resources
echo ""
echo -e "${YELLOW}System Resources:${NC}"

# CPU
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print 100 - $8}' | cut -d. -f1)
echo -e "  CPU:    ${CPU_USAGE}%"

# Memory
MEM_INFO=$(free -m | grep Mem)
MEM_USED=$(echo $MEM_INFO | awk '{print $3}')
MEM_TOTAL=$(echo $MEM_INFO | awk '{print $2}')
MEM_PCT=$((MEM_USED * 100 / MEM_TOTAL))
echo -e "  Memory: ${MEM_USED}MB / ${MEM_TOTAL}MB (${MEM_PCT}%)"

# GPU (if tegrastats available)
if command -v tegrastats &> /dev/null; then
    GPU_INFO=$(timeout 1 tegrastats --interval 100 2>/dev/null | head -1)
    if [ -n "$GPU_INFO" ]; then
        GPU_PCT=$(echo "$GPU_INFO" | grep -o 'GR3D_FREQ [0-9]*%' | grep -o '[0-9]*')
        echo -e "  GPU:    ${GPU_PCT}%"
    fi
fi

# Disk
DISK_INFO=$(df -h /home | tail -1)
DISK_USED=$(echo $DISK_INFO | awk '{print $3}')
DISK_TOTAL=$(echo $DISK_INFO | awk '{print $2}')
DISK_PCT=$(echo $DISK_INFO | awk '{print $5}')
echo -e "  Disk:   ${DISK_USED} / ${DISK_TOTAL} (${DISK_PCT})"

# Access URLs
echo ""
echo -e "${YELLOW}Access URLs:${NC}"
echo -e "  Frontend:  http://${JETSON_IP}:${FRONTEND_PORT}"
echo -e "  Backend:   http://${JETSON_IP}:${BACKEND_PORT}"
echo -e "  API Docs:  http://${JETSON_IP}:${BACKEND_PORT}/docs"
echo -e "  Stream:    http://${JETSON_IP}:${BACKEND_PORT}/api/stream/mjpeg"

echo ""
echo -e "${BLUE}============================================${NC}"
