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

# Check for .env file
if [ ! -f "backend/.env" ]; then
    echo -e "${YELLOW}No backend/.env file found.${NC}"
    echo "Creating from .env.example..."
    cp backend/.env.example backend/.env
    echo -e "${YELLOW}Please edit backend/.env and add your YOUTUBE_API_KEY${NC}"
    echo "Get one at: https://console.cloud.google.com/"
    echo ""
    echo "Then run ./dev.sh again."
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
    pip install -q mlx-whisper
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
