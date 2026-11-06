#!/usr/bin/env bash
# WardZero One-Click Startup Script for Linux / macOS / Git Bash
echo "============================================="
echo " Starting WardZero Healthcare Monitoring Demo"
echo "============================================="

# 1. Train synthetic Logistic Regression model if not present
if [ ! -f "ml/model.pkl" ]; then
    echo "[*] Training initial Scikit-Learn model on synthetic data..."
    python ml/train.py
fi

# 2. Start FastAPI Backend in background
echo "[*] Starting WardZero Backend (FastAPI on http://127.0.0.1:8000)..."
uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Wait 2 seconds for server boot
sleep 2

# 3. Start Telemetry Simulator in background
echo "[*] Starting Simulated Sensors (2-second interval telemetry)..."
python simulator/simulator.py &
SIM_PID=$!

echo "=========================================================="
echo " WardZero is running! Open your browser at:"
echo " -> http://127.0.0.1:8000"
echo " Press Ctrl+C in this terminal to shut down all processes."
echo "=========================================================="

trap "kill $BACKEND_PID $SIM_PID; exit" INT TERM
wait

