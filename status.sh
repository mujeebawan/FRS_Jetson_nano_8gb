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

    # Get system status
    STATUS=$(curl -s "http://localhost:$BACKEND_PORT/api/system/status" 2>/dev/null)
    if [ -n "$STATUS" ]; then
        FPS=$(echo "$STATUS" | grep -o '"fps":[0-9.]*' | cut -d: -f2)
        RUNNING=$(echo "$STATUS" | grep -o '"running":true' | wc -l)
        if [ "$RUNNING" -gt 0 ]; then
            echo -e "  Stream: ${GREEN}Active${NC} at ${FPS} FPS"
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

# Check Camera
echo ""
echo -e "${YELLOW}Camera (192.168.1.64):${NC}"
if ping -c 1 -W 1 192.168.1.64 > /dev/null 2>&1; then
    echo -e "  Status: ${GREEN}Reachable${NC}"
else
    echo -e "  Status: ${RED}Not reachable${NC}"
    echo -e "  ${YELLOW}Tip: Run 'sudo ip addr add 192.168.1.100/24 dev enP8p1s0'${NC}"
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
