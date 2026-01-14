#!/bin/bash
#
# Face Recognition Security System - Start Script
# Starts both backend (FastAPI) and frontend (React/Vite)
#

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/home/tempuser/Downloads/Frs_sec"
BACKEND_PORT=8000
FRONTEND_PORT=5173
BACKEND_LOG="/tmp/frs_backend.log"
FRONTEND_LOG="/tmp/frs_frontend.log"
PID_FILE="/tmp/frs.pid"

# Get Jetson IP
JETSON_IP=$(hostname -I | awk '{print $1}')

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Face Recognition Security System${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -i :$port > /dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to get PID using port
get_pid_on_port() {
    local port=$1
    lsof -t -i :$port 2>/dev/null | head -1
}

# Check if already running
echo -e "${YELLOW}Checking for existing processes...${NC}"

BACKEND_RUNNING=false
FRONTEND_RUNNING=false

if check_port $BACKEND_PORT; then
    BACKEND_PID=$(get_pid_on_port $BACKEND_PORT)
    echo -e "${GREEN}  Backend already running (PID: $BACKEND_PID)${NC}"
    BACKEND_RUNNING=true
fi

if check_port $FRONTEND_PORT; then
    FRONTEND_PID=$(get_pid_on_port $FRONTEND_PORT)
    echo -e "${GREEN}  Frontend already running (PID: $FRONTEND_PID)${NC}"
    FRONTEND_RUNNING=true
fi

if $BACKEND_RUNNING && $FRONTEND_RUNNING; then
    echo ""
    echo -e "${GREEN}System is already running!${NC}"
    echo ""
    echo -e "  Frontend: ${BLUE}http://${JETSON_IP}:${FRONTEND_PORT}${NC}"
    echo -e "  Backend:  ${BLUE}http://${JETSON_IP}:${BACKEND_PORT}${NC}"
    echo -e "  API Docs: ${BLUE}http://${JETSON_IP}:${BACKEND_PORT}/docs${NC}"
    echo ""
    echo -e "To stop: ${YELLOW}./stop.sh${NC}"
    exit 0
fi

# Setup network for camera (if not already done)
echo ""
echo -e "${YELLOW}Setting up camera network...${NC}"
if ! ip addr show enP8p1s0 2>/dev/null | grep -q "192.168.1.100"; then
    sudo ip addr add 192.168.1.100/24 dev enP8p1s0 2>/dev/null || true
    echo -e "  Added 192.168.1.100/24 to enP8p1s0"
else
    echo -e "  Network already configured"
fi

# Start Backend
if ! $BACKEND_RUNNING; then
    echo ""
    echo -e "${YELLOW}Starting Backend...${NC}"
    cd "$PROJECT_DIR"

    # Set Python path
    export PATH=$HOME/.local/bin:/usr/bin:$PATH
    export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

    # GPU optimization environment variables
    export CUDA_MODULE_LOADING=LAZY
    export TF_FORCE_GPU_ALLOW_GROWTH=true

    echo -e "  GPU Pipeline: DeepStream + TensorRT + FAISS GPU"

    # Start uvicorn in background
    nohup python3 -m uvicorn backend.app.main:app \
        --host 0.0.0.0 \
        --port $BACKEND_PORT \
        > "$BACKEND_LOG" 2>&1 &

    BACKEND_PID=$!
    echo "$BACKEND_PID" > "$PID_FILE"

    # Wait for backend to start
    echo -e "  Waiting for backend to initialize (loading AI models)..."
    for i in {1..30}; do
        if curl -s "http://localhost:$BACKEND_PORT/api/health" > /dev/null 2>&1; then
            echo -e "  ${GREEN}Backend started successfully (PID: $BACKEND_PID)${NC}"
            break
        fi
        sleep 1
        echo -n "."
    done
    echo ""

    # Check if actually running
    if ! curl -s "http://localhost:$BACKEND_PORT/api/health" > /dev/null 2>&1; then
        echo -e "  ${RED}Backend failed to start. Check log: $BACKEND_LOG${NC}"
        tail -20 "$BACKEND_LOG"
        exit 1
    fi
fi

# Start Frontend
if ! $FRONTEND_RUNNING; then
    echo ""
    echo -e "${YELLOW}Starting Frontend...${NC}"
    cd "$PROJECT_DIR/frontend"

    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo -e "  Installing dependencies (first run)..."
        npm install > /dev/null 2>&1
    fi

    # Start vite in background
    nohup npm run dev -- --host 0.0.0.0 > "$FRONTEND_LOG" 2>&1 &
    FRONTEND_PID=$!
    echo "$FRONTEND_PID" >> "$PID_FILE"

    # Wait for frontend
    echo -e "  Waiting for frontend to start..."
    for i in {1..15}; do
        if curl -s "http://localhost:$FRONTEND_PORT" > /dev/null 2>&1; then
            echo -e "  ${GREEN}Frontend started successfully (PID: $FRONTEND_PID)${NC}"
            break
        fi
        sleep 1
        echo -n "."
    done
    echo ""
fi

# Auto-start stream
echo ""
echo -e "${YELLOW}Starting camera stream...${NC}"
sleep 2
STREAM_RESPONSE=$(curl -s "http://localhost:$BACKEND_PORT/api/stream/start" 2>/dev/null)
if echo "$STREAM_RESPONSE" | grep -q '"success":true'; then
    echo -e "  ${GREEN}Camera stream started${NC}"
else
    echo -e "  ${YELLOW}Stream start response: $STREAM_RESPONSE${NC}"
fi

# Print access info
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  System Started Successfully!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "  ${BLUE}Pipeline:${NC}  DeepStream → TensorRT SCRFD → ArcFace → FAISS GPU"
echo ""
echo -e "  ${BLUE}Frontend:${NC}  http://${JETSON_IP}:${FRONTEND_PORT}"
echo -e "  ${BLUE}Backend:${NC}   http://${JETSON_IP}:${BACKEND_PORT}"
echo -e "  ${BLUE}API Docs:${NC}  http://${JETSON_IP}:${BACKEND_PORT}/docs"
echo -e "  ${BLUE}Stream:${NC}    http://${JETSON_IP}:${BACKEND_PORT}/api/stream/mjpeg"
echo ""
echo -e "  Logs:"
echo -e "    Backend:  ${YELLOW}tail -f $BACKEND_LOG${NC}"
echo -e "    Frontend: ${YELLOW}tail -f $FRONTEND_LOG${NC}"
echo ""
echo -e "  To stop: ${YELLOW}./stop.sh${NC}"
echo ""
