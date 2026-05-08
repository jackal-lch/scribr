#!/bin/bash

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check dependencies
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}Error: $1 is not installed.${NC}"
        echo "Install with: $2"
        exit 1
    fi
}

check_command python3 "brew install python (macOS) or apt install python3 (Linux)"
check_command node "brew install node (macOS) or apt install nodejs (Linux)"
check_command ffmpeg "brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"

# Check Python version (3.11+)
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "unknown")
    echo -e "${RED}Error: Python 3.11+ required, found $PY_VER.${NC}"
    echo "Install with: brew install python@3.11 (macOS) or apt install python3.11 (Linux)"
    exit 1
fi

# Check Node version (18+)
NODE_MAJOR=$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null)
if [ -z "$NODE_MAJOR" ] || [ "$NODE_MAJOR" -lt 18 ]; then
    NODE_VER=$(node -v 2>/dev/null || echo "unknown")
    echo -e "${RED}Error: Node 18+ required, found $NODE_VER.${NC}"
    echo "Install with: brew install node (macOS) or use nvm"
    exit 1
fi

# Check for .env file
if [ ! -f "backend/.env" ]; then
    echo -e "${YELLOW}No backend/.env file found.${NC}"
    echo "Creating from .env.example..."
    cp backend/.env.example backend/.env
    echo -e "${YELLOW}Please edit backend/.env and add your YOUTUBE_API_KEY${NC}"
    echo "Get one at: https://console.cloud.google.com/"
    echo ""
    echo "Then run ./start.sh again."
    exit 1
fi

# Verify YOUTUBE_API_KEY is filled in
API_KEY_LINE=$(grep "^YOUTUBE_API_KEY=" backend/.env || true)
if [ -z "$API_KEY_LINE" ] || [ "$API_KEY_LINE" = "YOUTUBE_API_KEY=" ] || [ "$API_KEY_LINE" = "YOUTUBE_API_KEY=your-youtube-api-key" ]; then
    echo -e "${RED}Error: YOUTUBE_API_KEY in backend/.env is not set.${NC}"
    echo "Edit backend/.env and add your YouTube Data API key."
    echo "Get one at: https://console.cloud.google.com/"
    exit 1
fi

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Stopping services...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo -e "${GREEN}Stopped.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Check ports are free
check_port() {
    local port=$1
    if command -v lsof >/dev/null 2>&1 && lsof -iTCP:$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${RED}Error: Port $port is already in use.${NC}"
        echo "Find the process: lsof -iTCP:$port -sTCP:LISTEN"
        exit 1
    fi
}
check_port 8000
check_port 5173

echo -e "${GREEN}Starting Scribr...${NC}"

# Setup backend
cd backend

# Create venv if it doesn't exist
if [ ! -d ".venv" ] && [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate 2>/dev/null || source venv/bin/activate 2>/dev/null

# Install/update Python dependencies
echo "Installing Python dependencies..."
pip install --progress-bar on -r requirements.txt

# Install mlx-whisper on macOS Apple Silicon (faster local transcription)
if [[ "$(uname)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
    echo "Installing mlx-whisper for Apple Silicon..."
    if ! pip install mlx-whisper; then
        echo -e "${YELLOW}Warning: mlx-whisper install failed. Falling back to faster-whisper (slower).${NC}"
    fi
fi

# Start backend (SQLite DB is created automatically)
echo "Starting backend..."
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Start frontend
echo "Starting frontend..."
cd frontend

# Install npm dependencies if node_modules doesn't exist or package.json changed
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo -e "${GREEN}Scribr is running:${NC}"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo "  Database: backend/scribr.db (SQLite)"
echo ""
echo "Press Ctrl+C to stop"

# Wait for both processes
wait
