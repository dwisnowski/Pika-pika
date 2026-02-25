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
        sample_rate = shm.header.sample_rate
        
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
            print(f"WS receive error: {e}")

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
        print("WebSocket client disconnected")
    except Exception as e:
        print(f"WebSocket send error: {e}")
    finally:
        listen_task.cancel()
