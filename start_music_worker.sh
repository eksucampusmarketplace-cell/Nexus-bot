#!/bin/bash
# Start Nexus Music Worker
# Run this on your local PC/WSL to start the music streaming worker

cd "$(dirname "$0")"

echo "============================================================"
echo "  🎵 NEXUS MUSIC WORKER"
echo "============================================================"

# Check if virtual environment exists
if [ -d ".venv" ]; then
    echo "[MUSIC_WORKER] Activating virtual environment..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "[MUSIC_WORKER] Activating virtual environment..."
    source venv/bin/activate
fi

# Load environment from .env.music
if [ -f ".env.music" ]; then
    echo "[MUSIC_WORKER] Loading environment from .env.music..."
    export $(grep -v '^#' .env.music | xargs)
else
    echo "[MUSIC_WORKER] ⚠️  .env.music not found! Using .env instead."
    if [ -f ".env" ]; then
        export $(grep -v '^#' .env | xargs)
    fi
fi

# Create download directory if it doesn't exist
mkdir -p "${MUSIC_DOWNLOAD_DIR:-/tmp/nexus_music}"

# Check for ffmpeg
echo "[MUSIC_WORKER] Checking dependencies..."
if command -v ffmpeg &> /dev/null; then
    echo "[MUSIC_WORKER] ✅ ffmpeg found"
else
    echo "[MUSIC_WORKER] ⚠️  ffmpeg not found! Music playback may not work."
    echo "[MUSIC_WORKER] Install with: sudo apt-get install ffmpeg"
fi

echo ""
echo "[MUSIC_WORKER] Starting music worker..."
echo "[MUSIC_WORKER] Press Ctrl+C to stop"
echo ""

# Run the worker with auto-restart
while true; do
    python3 music_worker_local.py 2>&1 | tee -a music_worker.log

    EXIT_CODE=${PIPESTATUS[0]}

    if [ $EXIT_CODE -eq 0 ] || [ $EXIT_CODE -eq 130 ]; then
        # Clean exit or Ctrl+C
        echo ""
        echo "[MUSIC_WORKER] Worker stopped cleanly."
        break
    fi

    echo ""
    echo "[MUSIC_WORKER] ⚠️  Worker crashed with exit code $EXIT_CODE"
    echo "[MUSIC_WORKER] Restarting in 5 seconds..."
    echo ""
    sleep 5
done
