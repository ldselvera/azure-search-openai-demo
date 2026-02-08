#!/bin/sh

# cd into the parent directory of the script, 
# so that the script generates virtual environments always in the same path.
cd "${0%/*}" || exit 1

cd ../

echo 'Creating python virtual environment ".venv"'
python3 -m venv .venv

echo ""
echo "Restoring backend python packages"
echo ""

./.venv/bin/python -m pip install -r app/backend/requirements.txt
out=$?
if [ $out -ne 0 ]; then
    echo "Failed to restore backend python packages"
    exit $out
fi

echo ""
echo "Starting FastAPI backend and Streamlit frontend"
echo ""

cd app/backend

# Start FastAPI backend in background
echo "Starting FastAPI backend on port 8000..."
../../.venv/bin/python -m uvicorn fastapi_app:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start Streamlit frontend
echo "Starting Streamlit frontend on port 8501..."
cd ..
BACKEND_URL=http://localhost:8000 ../../.venv/bin/streamlit run streamlit_app.py --server.port 8501 --server.address localhost &
FRONTEND_PID=$!

echo ""
echo "================================================"
echo "FastAPI backend running at: http://localhost:8000"
echo "Streamlit frontend running at: http://localhost:8501"
echo "================================================"
echo ""
echo "Press Ctrl+C to stop both services"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

# Trap SIGINT and SIGTERM
trap cleanup INT TERM

# Wait for either process to exit
wait $BACKEND_PID
wait $FRONTEND_PID
