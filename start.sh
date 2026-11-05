#!/bin/bash
# Start the Flask dashboard in the background
python dashboard.py &
DASHBOARD_PID=$!

# Optionally start tray companion if running with a desktop display
if [ -n "$DISPLAY" ]; then
    python tray.py &
    TRAY_PID=$!
fi

# Trap signals for graceful shutdown of background processes
trap "kill $DASHBOARD_PID $TRAY_PID 2>/dev/null || true; exit 0" SIGINT SIGTERM

# Start the main bot process in the foreground
python bot.py
