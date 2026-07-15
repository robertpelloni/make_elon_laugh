#!/bin/bash
# Start the Flask dashboard in the background
python dashboard.py &
# Start the main bot process in the foreground
python bot.py
