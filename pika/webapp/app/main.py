import asyncio
import glob
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

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

# Discrete physical acquisition rates for the oscilloscope / PRU slider.
ALLOWED_SAMPLE_RATES_HZ = (
    10, 20, 50, 100, 200, 500,
    1000, 2000, 5000, 10000, 20000, 50000,
    100000, 150000, 180000,
)
PIKA_BLOCK_SIZE = 128
ALIASING_WARN_BELOW_HZ = 120

_last_scope_total = None
_last_scope_progress_at = 0.0


def _scope_liveness_timeout_s(sample_rate: int) -> float:
    """Allow slow block fill at low rates (128 samples @ 10 S/s ≈ 12.8 s)."""
    if sample_rate <= 0:
        return 30.0
    block_period_s = PIKA_BLOCK_SIZE / float(sample_rate)
    return max(15.0, block_period_s * 2.5 + 5.0)


def _persist_nominal_rate_hz(config_path: Path, sample_rate: int) -> None:
    """Update only nominal_rate_hz so YAML comments/layout stay intact."""
    text = config_path.read_text()
    new_text, n = re.subn(
        r'(?m)^(  nominal_rate_hz:\s*)\d+(\b.*)$',
        rf'\g<1>{sample_rate}\2',
        text,
        count=1,
    )
    if n != 1:
        raise FileNotFoundError(
            f"Could not update nominal_rate_hz in {config_path}"
        )
    config_path.write_text(new_text)


def _pika_yaml_path() -> Path:
    config_path = Path(__file__).resolve().parents[2] / "pika.yaml"
    if not config_path.exists():
        config_path = Path("../pika.yaml")
    return config_path


def _persist_anomalies_config(config_path: Path, values: dict) -> None:
    """Update log-threshold fields in pika.yaml without rewriting the whole file."""
    text = config_path.read_text()
    replacements = [
        (
            r'(?m)^(  sag:\n(?:    .*\n)*?    threshold_pct:\s*)-?\d+(\b.*)$',
            rf'\g<1>{int(values["sag_threshold_pct"])}\2',
        ),
        (
            r'(?m)^(  sag:\n(?:    .*\n)*?    min_duration_ms:\s*)\d+(\b.*)$',
            rf'\g<1>{int(values["sag_min_duration_ms"])}\2',
        ),
        (
            r'(?m)^(  swell:\n(?:    .*\n)*?    threshold_pct:\s*)-?\d+(\b.*)$',
            rf'\g<1>{int(values["swell_threshold_pct"])}\2',
        ),
        (
            r'(?m)^(  swell:\n(?:    .*\n)*?    min_duration_ms:\s*)\d+(\b.*)$',
            rf'\g<1>{int(values["swell_min_duration_ms"])}\2',
        ),
        (
            r'(?m)^(  target_mains_vrms:\s*)[0-9.]+(\b.*)$',
            rf'\g<1>{float(values["target_mains_vrms"]):.1f}\2',
        ),
        (
            r'(?m)^(  sag_cooldown_ms:\s*)\d+(\b.*)$',
            rf'\g<1>{int(values["sag_cooldown_ms"])}\2',
        ),
        (
            r'(?m)^(  swell_cooldown_ms:\s*)\d+(\b.*)$',
            rf'\g<1>{int(values["swell_cooldown_ms"])}\2',
        ),
    ]
    for pattern, repl in replacements:
        text, n = re.subn(pattern, repl, text, count=1)
        if n != 1:
            raise FileNotFoundError(
                f"Could not update anomalies config in {config_path}"
            )
    config_path.write_text(text)


async def _restart_acquisition_service():
    """Restart PRU+datalogger+webapp after the HTTP response has flushed."""
    await asyncio.sleep(1.5)
    try:
        subprocess.Popen(
            ["sudo", "-n", "systemctl", "restart", "pika-run-all.service"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        logger.info("Scheduled restart of pika-run-all.service for sample-rate change")
    except Exception as e:
        logger.error(f"Failed to schedule acquisition restart: {e}")


def get_health_snapshot():
    """Return component health based on live PRU and scope-buffer progress."""
    from app.services.calibration_service import calibration_service

    global _last_scope_total, _last_scope_progress_at

    sample_rate = 0
    pru_clock_hz = 0
    sample_period_cycles = 0
    pru_state = "unknown"

    try:
        pru_found = False
        for name_file in glob.glob("/sys/class/remoteproc/remoteproc*/name"):
            with open(name_file, "r") as f:
                if "4a334000.pru" not in f.read().strip():
                    continue

            pru_found = True
            with open(name_file.replace("/name", "/state"), "r") as state_file:
                state = state_file.read().strip()
            if state == "running":
                pru_state = "running"
            elif state == "offline":
                pru_state = "offline"
            else:
                pru_state = "error"
            break

        if not pru_found:
            pru_state = "error"
    except Exception as e:
        logger.warning(f"Could not check PRU remoteproc state: {e}")
        pru_state = "error"

    now = time.monotonic()
    datalogger_running = False
    if shm.header and shm.header.magic == 0x5C09E000:
        sample_rate = shm.header.sample_rate
        pru_clock_hz = shm.header.pru_clock_hz
        sample_period_cycles = shm.header.sample_period_cycles
        current_total = shm.header.total_samples

        if _last_scope_total is None or current_total != _last_scope_total:
            _last_scope_total = current_total
            _last_scope_progress_at = now
        liveness_timeout = _scope_liveness_timeout_s(int(sample_rate or 0))
        datalogger_running = (
            current_total > 0 and now - _last_scope_progress_at < liveness_timeout
        )

    actual_sample_rate = 0
    if pru_clock_hz > 0 and sample_period_cycles > 0:
        actual_sample_rate = pru_clock_hz / sample_period_cycles

    calibration = calibration_service.get_calibration_values()
    learned_voltage = calibration["nominal_vrms"]
    learned_transformer_ratio = calibration["transformer_ratio"]
    learned_adc_vrms = (
        learned_voltage / learned_transformer_ratio
        if learned_transformer_ratio > 0
        else 0.0
    )

    return {
        "status": "ok",
        "pru_state": pru_state,
        "pru_connected": pru_state == "running",
        "datalogger_running": datalogger_running,
        "shm_magic": hex(shm.header.magic) if shm.header else "N/A",
        "sample_rate": sample_rate,
        "actual_sample_rate": actual_sample_rate,
        "pru_clock_hz": pru_clock_hz,
        "sample_period_cycles": sample_period_cycles,
        "learned_voltage": learned_voltage,
        "learned_adc_vrms": learned_adc_vrms,
        "learned_transformer_ratio": learned_transformer_ratio,
    }


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
    return get_health_snapshot()

# --- REST APIs ---

@app.get("/api/v1/history")
async def get_history_api():
    from app.services.history_service import history_service
    max_points = config_service.get_history_max_points()
    return history_service.get_decimated_data(max_points=max_points)


@app.get("/api/v1/history/rollup-10min")
async def get_history_rollup_api():
    """Best-effort 10-minute Vrms min/avg/max for ANSI C84.1 context."""
    from app.services.history_service import history_service
    return {"rollup_10min": history_service.get_vrms_10min_rollup(limit=144)}

@app.get("/api/v1/history/debug")
async def get_history_debug():
    """Debug endpoint: returns raw samples without calibration"""
    from app.services.history_service import history_service
    import struct
    import os
    
    path = os.path.join(history_service.data_dir, "decimated.bin")
    if not os.path.exists(path):
        return {"error": "decimated.bin not found", "path": path}
    
    samples_raw = []
    try:
        with open(path, "rb") as f:
            f.seek(0)
            chunk_idx = 0
            while f.tell() < os.path.getsize(path) and chunk_idx < 5:  # Read first 5 chunks only
                hdr_data = f.read(24)
                if len(hdr_data) < 24:
                    break
                ts, rate, count, channels, values_per_sample = struct.unpack("<QIIII", hdr_data)
                total_values = count * channels * values_per_sample
                raw_bytes = f.read(total_values * 2)
                if len(raw_bytes) < total_values * 2:
                    break
                shorts = struct.unpack(f"<{total_values}h", raw_bytes)
                if values_per_sample == 2:
                    ch0 = shorts[1::values_per_sample]
                else:
                    ch0 = shorts[0::values_per_sample]
                samples_raw.extend(ch0)
                chunk_idx += 1
    except Exception as e:
        return {"error": str(e)}
    
    return {
        "raw_samples_count": len(samples_raw),
        "first_20_raw": list(samples_raw[:20]),
        "min": min(samples_raw) if samples_raw else 0,
        "max": max(samples_raw) if samples_raw else 0,
        "mean": sum(samples_raw) / len(samples_raw) if samples_raw else 0
    }

@app.get("/api/v1/events")
async def get_events_api():
    from app.services.event_service import event_service
    return event_service.get_recent_events(limit=10)

@app.get("/api/v1/events/{event_id}/data")
async def get_event_data_api(event_id: int):
    from app.services.event_service import event_service
    logger.info(f"Fetching event data for event_id={event_id} (type: {type(event_id)})")
    data = event_service.get_event_data(event_id)
    if data is None:
        logger.warning(f"Event {event_id} not found")
        return {"error": "Event not found"}, 404
    logger.info(f"Successfully retrieved event {event_id}")
    return data

@app.get("/api/v1/config/sample-rate")
async def get_sample_rate():
    """Return the configured and allowed physical acquisition rates."""
    configured = config_service.get_nominal_rate_hz()
    live = 0
    if shm.header and shm.header.magic == 0x5C09E000:
        live = int(shm.header.sample_rate or 0)
    return {
        "sample_rate": live or configured,
        "configured_sample_rate": configured,
        "allowed_rates": list(ALLOWED_SAMPLE_RATES_HZ),
        "aliasing_warn_below_hz": ALIASING_WARN_BELOW_HZ,
    }


@app.post("/api/v1/config/sample-rate")
async def update_sample_rate(request: Request):
    """Update the physical ADC/PRU sample rate, persist it, and restart acquisition."""
    try:
        body = await request.json()
        sample_rate = int(body.get("sample_rate", 10000))

        if sample_rate not in ALLOWED_SAMPLE_RATES_HZ:
            return {
                "success": False,
                "error": (
                    f"Sample rate must be one of: "
                    f"{', '.join(str(r) for r in ALLOWED_SAMPLE_RATES_HZ)}"
                ),
                "allowed_rates": list(ALLOWED_SAMPLE_RATES_HZ),
            }

        config_path = _pika_yaml_path()
        if not config_path.exists():
            return {"success": False, "error": "Config file not found"}

        _persist_nominal_rate_hz(config_path, sample_rate)
        config_service.load_config()

        asyncio.create_task(_restart_acquisition_service())

        return {
            "success": True,
            "message": f"Sample rate updated to {sample_rate} Hz",
            "sample_rate": sample_rate,
            "restarting": True,
            "aliasing_warning": sample_rate < ALIASING_WARN_BELOW_HZ,
            "note": "Acquisition is restarting to apply the new rate",
        }

    except Exception as e:
        logger.exception("Failed to update sample rate")
        return {"success": False, "error": str(e)}


@app.get("/api/v1/config/anomalies")
async def get_anomalies_config():
    """Return user-editable log thresholds plus read-only review policy."""
    from app.services.review_policy import review_policy_public

    return {
        "log": config_service.get_anomalies_config(),
        "review": review_policy_public(config_service.config),
    }


@app.post("/api/v1/config/anomalies")
async def update_anomalies_config(request: Request):
    """Persist log thresholds to pika.yaml and restart acquisition."""
    try:
        body = await request.json()
        values = {
            "sag_threshold_pct": int(body.get("sag_threshold_pct", -10)),
            "swell_threshold_pct": int(body.get("swell_threshold_pct", 10)),
            "sag_min_duration_ms": int(body.get("sag_min_duration_ms", 9)),
            "swell_min_duration_ms": int(body.get("swell_min_duration_ms", 9)),
            "target_mains_vrms": float(body.get("target_mains_vrms", 120.0)),
            "sag_cooldown_ms": int(body.get("sag_cooldown_ms", 1000)),
            "swell_cooldown_ms": int(body.get("swell_cooldown_ms", 1000)),
        }

        if not (-50 <= values["sag_threshold_pct"] <= -1):
            return {"success": False, "error": "sag_threshold_pct must be between -50 and -1"}
        if not (1 <= values["swell_threshold_pct"] <= 50):
            return {"success": False, "error": "swell_threshold_pct must be between 1 and 50"}
        if not (1 <= values["sag_min_duration_ms"] <= 60000):
            return {"success": False, "error": "sag_min_duration_ms must be 1–60000"}
        if not (1 <= values["swell_min_duration_ms"] <= 60000):
            return {"success": False, "error": "swell_min_duration_ms must be 1–60000"}
        if not (90.0 <= values["target_mains_vrms"] <= 140.0):
            return {"success": False, "error": "target_mains_vrms must be 90–140 V"}
        if not (0 <= values["sag_cooldown_ms"] <= 60000):
            return {"success": False, "error": "sag_cooldown_ms must be 0–60000"}
        if not (0 <= values["swell_cooldown_ms"] <= 60000):
            return {"success": False, "error": "swell_cooldown_ms must be 0–60000"}

        config_path = _pika_yaml_path()
        if not config_path.exists():
            return {"success": False, "error": "Config file not found"}

        _persist_anomalies_config(config_path, values)
        config_service.load_config()
        asyncio.create_task(_restart_acquisition_service())

        return {
            "success": True,
            "message": "Anomaly log thresholds updated",
            "log": config_service.get_anomalies_config(),
            "restarting": True,
            "note": "Acquisition is restarting to apply new log thresholds",
        }
    except Exception as e:
        logger.exception("Failed to update anomalies config")
        return {"success": False, "error": str(e)}


@app.post("/api/v1/events/delete")
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
    last_health_sent = 0.0

    try:
        while True:
            payload = {}
            if not pause:
                samples = shm.get_window(req_window, req_channel)
                if samples:
                    effective_rate = len(samples) / req_window if req_window > 0 else 0
                    payload.update({
                        "samples": samples,
                        "time_window": req_window,
                        "channel": req_channel,
                        "effective_rate": effective_rate
                    })
                    if shm.last_raw_range:
                        payload["raw_min"] = shm.last_raw_range[0]
                        payload["raw_max"] = shm.last_raw_range[1]
                    if shm.last_adc_vrms is not None:
                        payload["adc_vrms"] = round(shm.last_adc_vrms, 6)
                        payload["adc_vref"] = shm.last_adc_vref
                        if shm.last_adc_vpp is not None:
                            payload["adc_vpp"] = round(shm.last_adc_vpp, 6)
            
            now = time.monotonic()
            if now - last_health_sent >= 2.0:
                payload["health"] = get_health_snapshot()
                last_health_sent = now

            if payload:
                await websocket.send_json(payload)

            # Throttle to 20Hz update (smooth UI)
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket send error: {e}")
    finally:
        listen_task.cancel()
