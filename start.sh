#!/bin/bash
#
# This script starts both the backend and frontend servers for local development.
# It also ensures that when you stop the script (Ctrl+C), both servers are properly shut down.

# Function to kill processes on exit
cleanup() {
    echo ""
    echo "Shutting down servers..."
    
    # Kill the backend uvicorn process if its PID was stored
    if [ -n "$backend_pid" ]; then
        kill $backend_pid
        echo "Backend server (PID: $backend_pid) stopped."
    fi
    
    # Kill the frontend python http.server process if its PID was stored
    if [ -n "$frontend_pid" ]; then
        kill $frontend_pid
        echo "Frontend server (PID: $frontend_pid) stopped."
    fi

    echo "Shutdown complete."
}

# Trap the EXIT signal to run the cleanup function. 
# This catches script termination from Ctrl+C (SIGINT) or other signals.
trap cleanup EXIT

# 1. Start the backend server using uv
echo "Starting backend server on http://localhost:8000..."
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
backend_pid=$! # Store the PID of the backend process

# 2. Start the frontend server
echo "Starting frontend server on http://localhost:8080..."
# The '-d' flag specifies the directory to serve, available in Python 3.7+
python3 -m http.server 8080 -d frontend &
frontend_pid=$! # Store the PID of the frontend process

echo
echo "----------------------------------------"
echo "✅ Application is running!"
echo
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:8080"
echo "----------------------------------------"
echo
echo "Press Ctrl+C to shut down both servers."
echo

# Wait indefinitely for the background jobs. The 'trap' will handle the exit.
wait 