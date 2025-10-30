#!/bin/bash

# Oracle Chat Development Startup Script
# This script starts both backend and frontend services for development

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[Oracle]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[Oracle]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[Oracle]${NC} $1"
}

print_error() {
    echo -e "${RED}[Oracle]${NC} $1"
}

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to cleanup processes on exit
cleanup() {
    print_status "Shutting down services..."
    
    if [ ! -z "$BACKEND_PID" ]; then
        print_status "Stopping backend (PID: $BACKEND_PID)..."
        kill $BACKEND_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$FRONTEND_PID" ]; then
        print_status "Stopping frontend (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    
    # Kill any remaining uvicorn or vite processes
    pkill -f "uvicorn main:app" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    
    print_success "Services stopped. Goodbye!"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

print_status "Starting Oracle Chat Development Environment..."
echo

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ] || [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Check for required files
if [ ! -f "backend/.env" ]; then
    print_warning "Backend .env file not found!"
    if [ -f "backend/.env.example" ]; then
        print_status "Copying .env.example to .env..."
        cp backend/.env.example backend/.env
        print_warning "Please edit backend/.env and add your GEMINI_API_KEY before continuing"
        print_status "You can get your API key from: https://aistudio.google.com/app/apikey"
        read -p "Press Enter after you've configured your API key..."
    else
        print_error "No .env.example file found in backend/"
        exit 1
    fi
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    print_status "Virtual environment not found. Creating one..."
    uv venv
    print_success "Virtual environment created"
fi

# Check if dependencies are installed
print_status "Checking backend dependencies..."
if ! source .venv/bin/activate && python -c "import fastapi, uvicorn" 2>/dev/null; then
    print_status "Installing backend dependencies..."
    uv pip install -e .
    print_success "Backend dependencies installed"
fi

# Check frontend dependencies
if [ ! -d "frontend/node_modules" ]; then
    print_status "Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
    print_success "Frontend dependencies installed"
fi

# Check if ports are available
if check_port 8000; then
    print_error "Port 8000 is already in use. Please stop the service using that port."
    exit 1
fi

if check_port 5173; then
    print_error "Port 5173 is already in use. Please stop the service using that port."
    exit 1
fi

print_success "Pre-flight checks completed!"
echo

# Create logs directory if it doesn't exist
if [ ! -d "logs" ]; then
    print_status "Creating logs directory..."
    mkdir -p logs
fi

# Start backend
print_status "Starting backend server..."
cd backend
source ../.venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000 > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
print_status "Waiting for backend to start..."
sleep 3

# Check if backend is running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    print_error "Backend failed to start. Check logs/backend.log for details."
    exit 1
fi

# Test backend health
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    print_success "Backend started successfully on http://localhost:8000"
else
    print_warning "Backend started but health check failed. It may still be initializing..."
fi

# Start frontend
print_status "Starting frontend server..."
cd frontend
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# Wait for frontend to start
print_status "Waiting for frontend to start..."
sleep 3

# Check if frontend is running
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    print_error "Frontend failed to start. Check logs/frontend.log for details."
    cleanup
    exit 1
fi

print_success "Frontend started successfully on http://localhost:5173"
echo

# Display status
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_success "🚀 Oracle Chat Development Environment is Ready!"
echo
echo "  📱 Frontend:  http://localhost:5173"
echo "  🔧 Backend:   http://localhost:8000"
echo "  📚 API Docs:  http://localhost:8000/docs"
echo "  ❤️  Health:    http://localhost:8000/health"
echo
echo "  📋 Logs:"
echo "    Backend:  tail -f logs/backend.log"
echo "    Frontend: tail -f logs/frontend.log"
echo
print_status "Press Ctrl+C to stop both services"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Keep script running and wait for interrupt
while true; do
    # Check if processes are still running
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        print_error "Backend process died unexpectedly!"
        break
    fi
    
    if ! kill -0 $FRONTEND_PID 2>/dev/null; then
        print_error "Frontend process died unexpectedly!"
        break
    fi
    
    sleep 5
done

cleanup