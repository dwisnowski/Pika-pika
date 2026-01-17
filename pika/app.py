"""FastAPI webserver that starts the datalogger and serves a Chart.js UI."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, JSONResponse
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

from .datalogger import Datalogger
from . import demo

app = FastAPI(title="Pika-pika")

# Lightweight CORS (adjust origins in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

def load_config():
    """Load configuration from config.toml file."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.toml")
    if not os.path.exists(config_path):
        # Create default config if it doesn't exist
        default_config = {
            "pika": {
                "sample_hz": 100,
                "data_dir": "data",
                "port": 8000,
                "display_fps": 5.0,
                "display_auto_ip": True
            }
        }
        return default_config["pika"]

    with open(config_path, "rb") as f:
        config = tomllib.load(f)
    return config.get("pika", {})

# Load configuration
config = load_config()
DATA_DIR = config.get("data_dir", "data")
SAMPLE_HZ = config.get("sample_hz", 100)
DISPLAY_FPS = config.get("display_fps", 5.0)
DISPLAY_AUTO_IP = config.get("display_auto_ip", True)

logger = Datalogger(data_dir=DATA_DIR, sample_hz=SAMPLE_HZ)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.sample_queue: Queue = Queue()
        self._broadcast_task = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                # Remove dead connections
                self.active_connections.remove(connection)

    def add_sample(self, ts: float, val: float):
        """Add a sample to the queue for broadcasting (thread-safe)."""
        try:
            # Use asyncio.create_task in a thread-safe way
            asyncio.run_coroutine_threadsafe(
                self.sample_queue.put((ts, val)),
                asyncio.get_event_loop()
            )
        except RuntimeError:
            # If no event loop, just queue it for later processing
            pass

    async def start_broadcast_task(self):
        """Start the background task that broadcasts samples to WebSocket clients."""
        if self._broadcast_task is None:
            self._broadcast_task = asyncio.create_task(self._broadcast_samples())

    async def _broadcast_samples(self):
        """Background task that processes the sample queue and broadcasts to clients."""
        while True:
            try:
                ts, val = await self.sample_queue.get()
                data_msg = {
                    "type": "new_sample",
                    "data": [ts, val]
                }
                await self.broadcast(json.dumps(data_msg))
                self.sample_queue.task_done()
            except Exception as e:
                print(f"Error broadcasting sample: {e}")
                await asyncio.sleep(0.1)


manager = ConnectionManager()

# static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.on_event("startup")
def startup_event():
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
        start_display(logger, auto_ip=DISPLAY_AUTO_IP, port=config.get("port", 8000), fps=DISPLAY_FPS, data_dir=DATA_DIR)
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
def api_highlights(start: float = None, end: float = None):
    """Get highlights, optionally filtered by time range.
    
    Args:
        start: Optional start timestamp (epoch seconds) to filter highlights
        end: Optional end timestamp (epoch seconds) to filter highlights
    """
    try:
        hl = getattr(app.state, '_highlights', None)
        if hl is not None:
            highlights = hl.get_highlights()
        else:
            # fallback: try reading from disk
            import json, os
            path = os.path.join(DATA_DIR, 'highlights.json')
            if os.path.exists(path):
                with open(path, 'r') as f:
                    highlights = json.load(f)
            else:
                highlights = []

        # Filter by time range if provided
        if start is not None or end is not None:
            filtered = []
            start_ts = float(start) if start is not None else None
            end_ts = float(end) if end is not None else None
            
            for h in highlights:
                # Check if highlight overlaps with the requested range
                # A highlight overlaps if: h.start_ts <= end AND h.end_ts >= start
                highlight_start = h.get('start_ts', 0)
                highlight_end = h.get('end_ts', highlight_start)
                
                if start_ts is not None and highlight_end < start_ts:
                    continue
                if end_ts is not None and highlight_start > end_ts:
                    continue
                    
                filtered.append(h)
            highlights = filtered

        return JSONResponse({"highlights": highlights})
    except Exception:
        import logging as _logging
        _logging.getLogger(__name__).exception("Error returning highlights")
    return JSONResponse({"highlights": []})

@app.get("/api/range")
def api_range(start: float, end: float, max_points: int = 1000):
    """Return downsampled data for the requested time range (epoch seconds)."""
    try:
        start = float(start)
        end = float(end)
        max_points = int(max_points)
    except Exception:
        return JSONResponse({"data": []})
    data = logger.get_range(start, end, max_points=max_points)
    return JSONResponse({"data": [[ts, val] for ts, val in data]})


@app.get("/api/config")
def get_config():
    """Get current configuration."""
    return JSONResponse({
        "sample_hz": logger.sample_hz,
        "data_dir": DATA_DIR,
        "port": config.get("port", 8000),
        "display_fps": DISPLAY_FPS,
        "display_auto_ip": DISPLAY_AUTO_IP
    })


@app.put("/api/config/sample-rate")
def update_sample_rate(sample_hz: int):
    """Update the sample rate (1-100 Hz)."""
    if sample_hz < 1 or sample_hz > 100:
        raise HTTPException(status_code=400, detail="Sample rate must be between 1 and 100 Hz")

    # Update the datalogger
    if logger.set_sample_rate(sample_hz):
        # Update config and save to file
        config["sample_hz"] = sample_hz
        config_path = os.path.join(os.path.dirname(__file__), "..", "config.toml")
        try:
            import tomli_w
            with open(config_path, "wb") as f:
                tomli_w.dump({"pika": config}, f)
        except ImportError:
            # If tomli_w not available, just update in memory
            pass

        # Broadcast the change to WebSocket clients
        asyncio.create_task(manager.broadcast(json.dumps({
            "type": "config_update",
            "config": {"sample_hz": sample_hz}
        })))

        return JSONResponse({"success": True, "sample_hz": sample_hz})
    else:
        return JSONResponse({"success": False, "message": "No change needed"})


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """WebSocket endpoint for real-time live data streaming."""
    await manager.connect(websocket)
    try:
        # Send initial recent data
        recent_data = logger.get_recent(seconds=5.0)
        if recent_data:
            data_msg = {
                "type": "recent_data",
                "data": [[ts, val] for ts, val in recent_data]
            }
            await websocket.send_text(json.dumps(data_msg))

        # Send initial highlights
        try:
            hl = getattr(app.state, '_highlights', None)
            highlights = []
            if hl is not None:
                highlights = hl.get_highlights()
            else:
                # fallback: try reading from disk
                import json as json_mod
                path = os.path.join(DATA_DIR, 'highlights.json')
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        highlights = json_mod.load(f)

            highlights_msg = {
                "type": "highlights",
                "highlights": highlights
            }
            await websocket.send_text(json.dumps(highlights_msg))
        except Exception:
            pass

        # Keep connection alive and listen for messages (though we don't expect any from client)
        while True:
            try:
                # Wait for any message from client (with timeout)
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send a ping to keep connection alive
                await websocket.send_text(json.dumps({"type": "ping"}))
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)


class DemoConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._demo_task = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        if not self._demo_task:
            self._demo_task = asyncio.create_task(self._run_demo_simulation())

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        if not self.active_connections:
            if self._demo_task:
                self._demo_task.cancel()
                self._demo_task = None

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                # Remove dead connections
                self.active_connections.remove(connection)

    async def _run_demo_simulation(self):
        """Simulate real-time demo data by generating consistent voltage with occasional anomalies."""
        import random
        
        # Track active anomalies for real-time generation
        active_anomalies = []  # List of (end_time, magnitude, type, start_time, center)
        next_anomaly_time = None
        anomaly_counter = 0

        # Send initial data
        now = time.time()
        initial_points = demo.recent(seconds=5.0, max_points=500)
        if initial_points:
            data_msg = {
                "type": "recent_data",
                "data": [[ts, val] for ts, val in initial_points]
            }
            await self.broadcast(json.dumps(data_msg))

        # Send initial highlights
        highlights = demo.highlights_for_range(now - 3600, now)
        highlights_msg = {
            "type": "highlights",
            "highlights": highlights
        }
        await self.broadcast(json.dumps(highlights_msg))

        # Simulate real-time data
        sample_count = 0
        base_voltage = 1.5
        while self.active_connections:
            try:
                t = time.time()
                
                # Remove expired anomalies
                active_anomalies = [a for a in active_anomalies if a[0] > t]
                
                # Occasionally trigger a new anomaly (every 15-45 seconds randomly)
                if next_anomaly_time is None:
                    # Schedule next anomaly in 15-45 seconds
                    next_anomaly_time = t + random.uniform(15, 45)
                elif t >= next_anomaly_time:
                    # Trigger a new anomaly
                    anomaly_counter += 1
                    duration = random.uniform(2, 8)  # 2-8 seconds
                    is_spike = random.random() > 0.4  # 60% chance spike, 40% drop
                    
                    if is_spike:
                        magnitude = random.uniform(0.6, 1.5)  # Positive spike
                        anom_type = 'spike'
                    else:
                        magnitude = random.uniform(-1.2, -0.5)  # Negative drop
                        anom_type = 'drop'
                    
                    center = t
                    start_time = center - duration / 2.0
                    end_time = center + duration / 2.0
                    
                    active_anomalies.append((end_time, magnitude, anom_type, start_time, center))
                    next_anomaly_time = None  # Schedule next one
                
                # Generate consistent base voltage with small noise
                voltage = base_voltage + random.uniform(-0.005, 0.005)
                
                # Apply active anomalies
                for end_time, magnitude, anom_type, start_time, center in active_anomalies:
                    if start_time <= t <= end_time:
                        # Calculate envelope (bell curve shape)
                        span = end_time - start_time
                        env = 1.0 - abs((t - center) / (span / 2.0))
                        voltage += magnitude * env

                # Send new sample
                sample_msg = {
                    "type": "new_sample",
                    "data": [t, voltage]
                }
                await self.broadcast(json.dumps(sample_msg))

                # Occasionally update highlights (including new anomalies)
                sample_count += 1
                if sample_count % 100 == 0:  # Every ~10 seconds at 10Hz simulation
                    highlights = demo.highlights_for_range(t - 3600, t)
                    
                    # Add any recently triggered real-time anomalies to highlights
                    for end_time, magnitude, anom_type, start_time, center in active_anomalies:
                        if start_time >= t - 3600:  # Within last hour
                            highlights.append({
                                'start_ts': start_time,
                                'end_ts': end_time,
                                'peak_ts': center,
                                'peak_value': base_voltage + magnitude,
                                'duration': end_time - start_time,
                                'score': abs(magnitude) * (end_time - start_time),
                                'type': anom_type
                            })
                    
                    highlights_msg = {
                        "type": "highlights",
                        "highlights": highlights
                    }
                    await self.broadcast(json.dumps(highlights_msg))

                await asyncio.sleep(0.1)  # 10Hz simulation

            except Exception as e:
                print(f"Demo simulation error: {e}")
                await asyncio.sleep(1.0)


demo_manager = DemoConnectionManager()


@app.websocket("/ws/demo")
async def websocket_demo(websocket: WebSocket):
    """WebSocket endpoint for real-time demo data streaming."""
    await demo_manager.connect(websocket)
    try:
        # Keep connection alive
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    finally:
        demo_manager.disconnect(websocket)


# --- Demo endpoints (mocked data for preview without hardware) ---
@app.get('/demo')
def demo_page():
    """Serve the demo static page which pulls mocked data."""
    return FileResponse(os.path.join(static_dir, 'demo.html'))


@app.get('/history')
def history_page():
    """Serve the history static page for viewing historical data."""
    return FileResponse(os.path.join(static_dir, 'history.html'))


@app.get('/api/demo/recent')
def api_demo_recent(seconds: float = 20.0, max_points: int = 2000):
    pts = demo.recent(seconds=seconds, max_points=max_points)
    return JSONResponse({'points': [[ts, v] for ts, v in pts]})


@app.get('/api/demo/range')
def api_demo_range(start: float, end: float, max_points: int = 2000):
    try:
        start = float(start)
        end = float(end)
        max_points = int(max_points)
    except Exception:
        return JSONResponse({'points': []})
    pts = demo.range_query(start, end, max_points=max_points)
    return JSONResponse({'points': [[ts, v] for ts, v in pts]})


@app.get('/api/demo/highlights')
def api_demo_highlights(start: float = None, end: float = None):
    now = time.time()
    if start is None: start = now - 3 * 3600
    if end is None: end = now
    h = demo.highlights_for_range(start, end)
    return JSONResponse(h)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("pika.app:app", host="0.0.0.0", port=8000, log_level="info")
