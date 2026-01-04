#!/bin/bash

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Stopping services...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    docker-compose down
    echo -e "${GREEN}Stopped.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo -e "${GREEN}Starting Scribr...${NC}"

# Start database
docker-compose up -d
sleep 2

# Run migrations
echo "Running migrations..."
cd backend
source .venv/bin/activate 2>/dev/null || source venv/bin/activate 2>/dev/null
alembic upgrade head

# Start backend
echo "Starting backend..."
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Start frontend
echo "Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo -e "${GREEN}Scribr is running:${NC}"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop"

# Wait for both processes
wait
