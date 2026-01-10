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

@app.on_event("shutdown")
def shutdown_event():
    logger.stop()

@app.get("/")
def index():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/api/recent")
def api_recent(seconds: float = 5.0):
    data = logger.get_recent(seconds=seconds)
    return JSONResponse({"data": [[ts, val] for ts, val in data]})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("pika.app:app", host="0.0.0.0", port=8000, log_level="info")
