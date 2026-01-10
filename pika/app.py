"""FastAPI webserver that starts the datalogger and serves a Chart.js UI."""
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from .datalogger import Datalogger

app = FastAPI(title="Pika-pika")

# Lightweight CORS (adjust origins in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

DATA_DIR = os.environ.get("PIKA_DATA_DIR", "data")
SAMPLE_HZ = int(os.environ.get("PIKA_SAMPLE_HZ", "100"))
logger = Datalogger(data_dir=DATA_DIR, sample_hz=SAMPLE_HZ)

# static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.on_event("startup")
def startup_event():
    # Restore recent samples from disk and start sampling
    logger.tail_from_disk(seconds=30)
    logger.start()
    # start the display manager (renders QR and animation if display available)
    try:
        from .display_manager import start_display
        display_port = int(os.environ.get("PIKA_PORT", "8000"))
        start_display(logger, auto_ip=True, port=display_port, fps=5.0)
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


@app.get('/health')
def health():
    """Simple health endpoint useful for monitoring and systemd checks.

    Returns:
      - status: 'ok' | 'degraded' | 'fail'
      - last_sample_age: seconds since last sample (or null if none)
      - recent_count: number of recent samples in 10s window
    """
    import time as _time
    recent = logger.get_recent(seconds=10.0)
    last_sample_age = None
    if recent:
        last_sample_age = _time.time() - recent[-1][0]
    status = 'ok'
    if last_sample_age is None or last_sample_age > 3.0:
        status = 'degraded'
    return JSONResponse({"status": status, "last_sample_age": last_sample_age, "recent_count": len(recent)})

@app.get("/")
def index():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/api/recent")
def api_recent(seconds: float = 5.0):
    data = logger.get_recent(seconds=seconds)
    return JSONResponse({"data": [[ts, val] for ts, val in data]})

@app.get("/api/highlights")
def api_highlights():
    try:
        hl = getattr(app.state, '_highlights', None)
        if hl is not None:
            return JSONResponse({"highlights": hl.get_highlights()})
        # fallback: try reading from disk
        import json, os
        path = os.path.join(DATA_DIR, 'highlights.json')
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
            return JSONResponse({"highlights": data})
    except Exception:
        import logging as _logging
        _logging.getLogger(__name__).exception("Error returning highlights")
    return JSONResponse({"highlights": []})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("pika.app:app", host="0.0.0.0", port=8000, log_level="info")
