import asyncio
import json
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.core.config import settings
from app.services.shared_memory import shm

app = FastAPI(title="Pika Power Monitor")

# Templates and Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
async def startup_event():
    try:
        shm.connect()
        print("Connected to PRU Shared Memory")
    except Exception as e:
        print(f"Warning: Could not connect to SHM: {e}")

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
    sample_rate = 0
    if shm.header:
        # PRU runs at 200MHz
        sample_rate = 200000000 // shm.header.sample_period_cycles
        
    return {
        "status": "ok",
        "pru_connected": shm.header is not None,
        "shm_magic": hex(shm.header.magic) if shm.header else "N/A",
        "sample_rate": sample_rate
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

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket client connected")
    try:
        while True:
            # Poll SHM for latest block
            result = shm.get_latest_samples()
            if result:
                desc, samples = result
                # Serialize to JSON and send
                # We send it as a flat list of shorts
                await websocket.send_json({
                    "ts": desc.timestamp_cycles,
                    "samples": samples
                })
            
            # Throttle to avoid flooding the socket
            # 50Hz update rate is plenty for smooth visualizer
            await asyncio.sleep(0.02)
    except WebSocketDisconnect:
        print("WebSocket client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
