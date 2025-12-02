#!/bin/bash
#
# Face Recognition Security System - Stop Script
# Stops both backend and frontend services
#

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BACKEND_PORT=8000
FRONTEND_PORT=5173
PID_FILE="/tmp/frs.pid"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Stopping Face Recognition System${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Function to kill process on port
kill_on_port() {
    local port=$1
    local name=$2
    local pids=$(lsof -t -i :$port 2>/dev/null)

    if [ -n "$pids" ]; then
        echo -e "${YELLOW}Stopping $name (port $port)...${NC}"
        for pid in $pids; do
            kill -9 $pid 2>/dev/null
            echo -e "  Killed PID: $pid"
        done
        return 0
    else
        echo -e "  $name not running on port $port"
        return 1
    fi
}

# Stop backend
kill_on_port $BACKEND_PORT "Backend"

# Stop frontend
kill_on_port $FRONTEND_PORT "Frontend"

# Also kill any remaining uvicorn/node processes for this project
echo ""
echo -e "${YELLOW}Cleaning up any remaining processes...${NC}"
pkill -9 -f "uvicorn backend.app.main" 2>/dev/null && echo "  Killed uvicorn processes" || true
pkill -9 -f "vite.*frs" 2>/dev/null && echo "  Killed vite processes" || true

# Remove PID file
if [ -f "$PID_FILE" ]; then
    rm -f "$PID_FILE"
fi

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  System Stopped${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "  To start again: ${YELLOW}./start.sh${NC}"
echo ""
