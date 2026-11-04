"""
Emperor Musk Bot - System Tray Companion (tray.py)

Provides a background system tray icon for desktop environments (macOS, Windows, Linux).
Offers quick access to:
- Dashboard (opens in default web browser)
- Trigger On-demand Dry-Run Check
- Display current status
- Gracefully shut down both bot and dashboard servers

In headless, containerized, or non-GUI environments, gracefully falls back or logs
helpful instructions rather than crashing.
"""

import logging
import os
import signal
import sys
import time
import urllib.error
import urllib.request
import webbrowser

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TRAY_AVAILABLE = False
try:
    from PIL import Image, ImageDraw
    import pystray
    TRAY_AVAILABLE = True
except (ImportError, Exception):
    TRAY_AVAILABLE = False


def generate_tray_icon_image():
    """Generates a small 64x64 icon for the system tray (a UFO / space motif)."""
    image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    # Background circle
    draw.ellipse((4, 4, 60, 60), fill=(29, 155, 240, 255))
    # Dome
    draw.chord((20, 14, 44, 38), 180, 360, fill=(255, 255, 255, 255))
    # Saucer disk
    draw.ellipse((10, 28, 54, 44), fill=(247, 249, 249, 255))
    # Small beam lights
    draw.ellipse((18, 38, 24, 42), fill=(0, 186, 124, 255))
    draw.ellipse((30, 40, 34, 44), fill=(255, 212, 0, 255))
    draw.ellipse((40, 38, 46, 42), fill=(249, 24, 128, 255))
    return image


def open_dashboard():
    """Opens the web dashboard in the default browser."""
    url = "http://localhost:5000"
    logging.info(f"Opening dashboard at {url}")
    webbrowser.open(url)


def trigger_check():
    """Triggers an on-demand dry run check via dashboard API."""
    logging.info("Triggering dry run check via API...")
    try:
        req = urllib.request.Request(
            "http://localhost:5000/api/run-check",
            data=b"{}",
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            logging.info(f"Check response: {response.read().decode('utf-8')}")
    except Exception as e:
        logging.warning(f"Could not reach dashboard API: {e}")


def quit_servers(icon=None):
    """Signals all running bot & dashboard servers to terminate gracefully."""
    logging.info("🛑 Quitting servers from tray icon...")
    try:
        # Call shutdown endpoint
        req = urllib.request.Request(
            "http://localhost:5000/api/shutdown",
            data=b"{}",
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass

    if icon:
        icon.stop()

    time.sleep(0.5)
    try:
        os.kill(0, signal.SIGTERM)
    except Exception:
        pass


def run_tray():
    """Initializes and runs the system tray menu loop."""
    if not TRAY_AVAILABLE:
        logging.info("Desktop system tray libraries not available or GUI unavailable. Running in headless mode.")
        return False

    # Check if DISPLAY or OS supports system tray
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        logging.info("No DISPLAY detected. Running in headless server mode.")
        return False

    try:
        image = generate_tray_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("🛸 Open Dashboard", lambda: open_dashboard()),
            pystray.MenuItem("⚡ Trigger Check Cycle", lambda: trigger_check()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🛑 Quit Servers", lambda icon, item: quit_servers(icon))
        )
        icon = pystray.Icon("emperor_musk_bot", image, "Emperor Musk Bot", menu=menu)
        logging.info("System tray companion initialized.")
        icon.run()
        return True
    except Exception as e:
        logging.warning(f"Could not initialize system tray GUI (likely headless environment): {e}")
        return False


if __name__ == "__main__":
    run_tray()
