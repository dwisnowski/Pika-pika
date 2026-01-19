"""FastAPI webserver that starts the datalogger and serves a Chart.js UI."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import time
import json
import asyncio
from typing import List
from asyncio import Queue
try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback for older versions

from fastapi.templating import Jinja2Templates
from .datalogger import Datalogger
from . import demo
from .handlers import register_all_routes, register_websocket_demo_routes
from .websocket import ConnectionManager, DemoConnectionManager

app = FastAPI(title="Pika-pika")

# Initialize Jinja2 templates
templates = Jinja2Templates(directory="pika/templates")

# Lightweight CORS (adjust origins in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS", "HEAD", "PUT", "DELETE"],
    allow_headers=["*"],
    allow_credentials=True,
)

def load_config():
    """Load configuration from config.toml file."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.toml")
    if not os.path.exists(config_path):
        # Create default config if it doesn't exist
        return {
            "pika": {
                "sample_hz": 100,
                "data_dir": "data",
                "port": 8000,
                "display_fps": 5.0,
                "display_auto_ip": True
            },
            "pins": {
                "adc_address": 0x48,
                "adc_channel": 0,
                "lcd_port": 0,
                "lcd_device": 0,
                "lcd_cs": 8,
                "lcd_dc": 25,
                "lcd_rst": 27,
                "lcd_bl": 24
            }
        }

    with open(config_path, "rb") as f:
        return tomllib.load(f)

# Load configuration
full_config = load_config()
config = full_config.get("pika", {})
pins = full_config.get("pins", {})
dl_config = full_config.get("datalogger", {})
analysis_config = full_config.get("analysis", {})

DATA_DIR = config.get("data_dir", "data")
SAMPLE_HZ = config.get("sample_hz", 100)
DISPLAY_FPS = config.get("display_fps", 5.0)
DISPLAY_AUTO_IP = config.get("display_auto_ip", True)

logger = Datalogger(
    data_dir=DATA_DIR, 
    sample_hz=SAMPLE_HZ,
    adc_address=pins.get("adc_address", 0x48),
    adc_channel=pins.get("adc_channel", 0),
    batch_size=dl_config.get("batch_size", 400),
    batch_interval_ms=dl_config.get("batch_interval_ms", 1000),
    analysis_config=analysis_config
)

manager = ConnectionManager()
demo_manager = DemoConnectionManager(data_dir=DATA_DIR)

# static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Automatically register all routes from handlers package
register_all_routes(app, logger, config, manager, static_dir, DISPLAY_FPS, DISPLAY_AUTO_IP, DATA_DIR)

# Register demo WebSocket route (has dependency on demo_manager)
register_websocket_demo_routes(app, demo_manager)

@app.on_event("startup")
def startup_event():
    # Clear demo files to ensure each run starts fresh
    demo_csv = os.path.join(DATA_DIR, "demo.csv")
    demo_highlights = os.path.join(DATA_DIR, "demo_highlights.json")
    for f in [demo_csv, demo_highlights]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                import logging as _logging
                _logging.getLogger(__name__).exception(f"Failed to remove {f}")

    # Restore recent samples from disk and start sampling
    logger.tail_from_disk(seconds=30)
    logger.start()

    # Start the WebSocket broadcast task
    asyncio.create_task(manager.start_broadcast_task())

    # Register WebSocket callback for real-time data
    def sync_callback(ts, val):
        """Thread-safe callback to add samples to broadcast queue."""
        manager.add_sample(ts, val)

    logger.add_sample_callback(sync_callback)
    # start the display manager (renders QR and animation if display available)
    try:
        from .display_manager import start_display
        start_display(
            logger, 
            auto_ip=DISPLAY_AUTO_IP, 
            port=config.get("port", 8000), 
            fps=DISPLAY_FPS, 
            data_dir=DATA_DIR,
            lcd_config=pins
        )
    except Exception:
        # non-fatal: continue if display is not available
        import logging as _logging
        _logging.getLogger(__name__).exception("Could not start display manager")

    # start systemd watchdog notifier (if available)
    try:
        from .watchdog import start_watchdog
        # Pass the datalogger to allow watchdog to verify fresh samples
        _wd = start_watchdog(datalogger=logger, stale_threshold=3.0)
        # store on app state for shutdown
        app.state._watchdog = _wd
    except Exception:
        import logging as _logging
        _logging.getLogger(__name__).exception("Could not start systemd watchdog notifier")

    # start highlights manager (anomaly detection)
    try:
        from .highlights import start_highlights
        _hl = start_highlights(logger, data_dir=DATA_DIR)
        app.state._highlights = _hl
    except Exception:
        import logging as _logging
        _logging.getLogger(__name__).exception("Could not start highlights manager")

@app.on_event("shutdown")
def shutdown_event():
    # stop watchdog, display then datalogger
    try:
        wd = getattr(app.state, '_watchdog', None)
        if wd is not None:
            from .watchdog import stop_watchdog
            stop_watchdog(wd)
    except Exception:
        import logging as _logging
        _logging.getLogger(__name__).exception("Error stopping watchdog")

    try:
        from .display_manager import stop_display
        stop_display()
    except Exception:
        import logging as _logging
        _logging.getLogger(__name__).exception("Error stopping display manager")
    logger.stop()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("pika.app:app", host="0.0.0.0", port=8000, log_level="info")
