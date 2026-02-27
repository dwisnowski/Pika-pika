import asyncio
import json
import time
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.core.config import settings
from app.services.shared_memory import shm
from app.services.config_service import config_service

app = FastAPI(title="Pika Power Monitor")

# Configure logging based on config file
log_level = config_service.get_log_level().upper()
log_level_enum = getattr(logging, log_level, logging.INFO)

# Configure root logger
logging.basicConfig(
    level=log_level_enum,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Configure uvicorn loggers
logging.getLogger("uvicorn").setLevel(log_level_enum)
logging.getLogger("uvicorn.access").setLevel(log_level_enum)
logging.getLogger("uvicorn.error").setLevel(log_level_enum)

logger = logging.getLogger(__name__)

# Templates and Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
async def startup_event():
    try:
        shm.connect()
        logger.info("Connected to PRU Shared Memory")
    except Exception as e:
        logger.warning(f"Could not connect to SHM: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    shm.cleanup()

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/oscilloscope", response_class=HTMLResponse)
async def get_oscilloscope(request: Request):
    return templates.TemplateResponse("oscilloscope.html", {"request": request})

@app.get("/events", response_class=HTMLResponse)
async def get_events_view(request: Request):
    return templates.TemplateResponse("events.html", {"request": request})

@app.get("/health")
async def health():
    from app.services.calibration_service import calibration_service
    
    sample_rate = 0
    pru_clock_hz = 0
    sample_period_cycles = 0
    
    if shm.header:
        sample_rate = shm.header.sample_rate
        pru_clock_hz = shm.header.pru_clock_hz
        sample_period_cycles = shm.header.sample_period_cycles
    
    # Calculate actual sample rate from PRU timing
    actual_sample_rate = 0
    if pru_clock_hz > 0 and sample_period_cycles > 0:
        actual_sample_rate = pru_clock_hz / sample_period_cycles
    
    learned_voltage = calibration_service.get_learned_voltage()
        
    return {
        "status": "ok",
        "pru_connected": shm.header is not None,
        "shm_magic": hex(shm.header.magic) if shm.header else "N/A",
        "sample_rate": sample_rate,
        "actual_sample_rate": actual_sample_rate,
        "pru_clock_hz": pru_clock_hz,
        "sample_period_cycles": sample_period_cycles,
        "learned_voltage": learned_voltage
    }

# --- REST APIs ---

@app.get("/api/v1/history")
async def get_history_api():
    from app.services.history_service import history_service
    return history_service.get_decimated_data(max_points=500)

@app.get("/api/v1/events")
async def get_events_api():
    from app.services.event_service import event_service
    return event_service.get_recent_events(limit=10)

@app.post("/api/v1/config/sample-rate")
async def update_sample_rate(request: Request):
    """Update the ADC sample rate and persist to config file."""
    try:
        body = await request.json()
        sample_rate = int(body.get("sample_rate", 10000))
        
        # Validate range
        if sample_rate < 1000 or sample_rate > 100000:
            return {"success": False, "error": "Sample rate must be between 1000 and 100000 Hz"}
        
        # Update the datalogger config file
        import yaml
        from pathlib import Path
        
        config_path = Path("../pika.yaml")
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Update the sample rate
            if 'sampling' not in config:
                config['sampling'] = {}
            config['sampling']['nominal_rate_hz'] = sample_rate
            
            # Write back to file
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            # Update the global config in memory
            from app.services.calibration_service import config_service
            global_config_updated = True
            
            return {
                "success": True,
                "message": f"Sample rate updated to {sample_rate} Hz",
                "sample_rate": sample_rate,
                "note": "Restart datalogger for changes to take effect"
            }
        else:
            return {"success": False, "error": "Config file not found"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}
async def delete_events_api():
    """Delete all event data from the datalogger storage."""
    from app.services.event_service import event_service
    import os
    
    try:
        events_path = os.path.join(event_service.data_dir, "events.bin")
        index_path = os.path.join(event_service.data_dir, "index.bin")
        
        # Check if files exist
        if not os.path.exists(events_path) and not os.path.exists(index_path):
            return {"error": "No event data found"}
        
        # Delete the files
        deleted = []
        for path in [events_path, index_path]:
            if os.path.exists(path):
                os.remove(path)
                deleted.append(os.path.basename(path))
        
        return {
            "success": True,
            "message": f"Deleted {', '.join(deleted)}",
            "deleted_files": deleted
        }
    except Exception as e:
        return {"error": str(e), "success": False}, 500

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket client connected")
    
    # Defaults
    req_window = 0.1  # 100ms default view
    req_channel = 0
    pause = False

    async def receive_messages():
        nonlocal req_window, req_channel, pause
        try:
            while True:
                data = await websocket.receive_json()
                if "time_window" in data:
                    req_window = float(data["time_window"])
                if "channel" in data:
                    req_channel = int(data["channel"])
                if "pause" in data:
                    pause = bool(data["pause"])
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"WS receive error: {e}")

    # Spin up async listener
    listen_task = asyncio.create_task(receive_messages())

    try:
        while True:
            if not pause:
                samples = shm.get_window(req_window, req_channel)
                if samples:
                    effective_rate = len(samples) / req_window if req_window > 0 else 0
                    await websocket.send_json({
                        "samples": samples,
                        "time_window": req_window,
                        "channel": req_channel,
                        "effective_rate": effective_rate
                    })
            
            # Throttle to 20Hz update (smooth UI)
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket send error: {e}")
    finally:
        listen_task.cancel()
