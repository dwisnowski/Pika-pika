"""Configuration API endpoint handlers.

Provides access to current configuration and allows updating sample rate.
"""

import json
import os
from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.responses import JSONResponse

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib # Fallback
    except ImportError:
        tomllib = None

try:
    import tomlkit
except ImportError:
    tomlkit = None

router = APIRouter()

# Global variables to hold instances passed during registration
logger = None
config = None
manager = None
display_fps = None
display_auto_ip = None


@router.put("/config/analysis")
async def update_analysis_config(data: dict):
    """Update analysis configuration and save to file."""
    try:
        if logger:
            logger.update_analysis_config(data)
            _save_to_config("analysis", data)
        return {"success": True, "config": (logger.analysis_config if logger else {})}
    except Exception as e:
        return {"success": False, "error": str(e)}

def _save_to_config(section: str, updates: dict):
    """Helper to save specific config updates while preserving comments using tomlkit."""
    if not tomlkit:
        return
        
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "config.toml")
    if not os.path.exists(config_path):
        return

    try:
        with open(config_path, "r") as f:
            content = f.read()
            doc = tomlkit.parse(content)
        
        if section not in doc:
            doc[section] = tomlkit.table()
            
        for k, v in updates.items():
            doc[section][k] = v
            
        with open(config_path, "w") as f:
            f.write(tomlkit.dumps(doc))
    except Exception as e:
        print(f"Failed to save to config: {e}")

@router.get("/config/analysis")
async def get_analysis_config():
    """Get current analysis configuration."""
    if logger:
        return logger.analysis_config
    return {}


@router.get("/config")
async def get_current_config():
    """Get current configuration."""
    return get_config(logger, config, display_fps, display_auto_ip)

@router.put("/config/sample-rate")
async def handle_update_sample_rate(data: dict):
    """Update the sample rate."""
    return update_sample_rate(logger, config, manager, data)

@router.put("/config/adc-channel")
async def handle_update_adc_channel(data: dict):
    """Update the ADC channel."""
    return update_adc_channel(logger, config, manager, data)


def register_api_config_routes(app: FastAPI, _logger, _config, _manager, _display_fps, _display_auto_ip):
    """Register configuration API routes with the FastAPI app."""
    global logger, config, manager, display_fps, display_auto_ip
    logger = _logger
    config = _config
    manager = _manager
    display_fps = _display_fps
    display_auto_ip = _display_auto_ip

    app.include_router(router, prefix="/api")


def get_config(logger, config, display_fps, display_auto_ip):
    """Get current configuration.
    
    Args:
        logger: Datalogger instance
        config: Configuration dictionary
        display_fps: Display FPS setting
        display_auto_ip: Display auto IP setting
        
    Returns:
        JSON response with current configuration
    """
    return JSONResponse({
        "sample_hz": logger.sample_hz,
        "adc_channel": (logger.adc.channel if hasattr(logger.adc, 'channel') else 0),
        "data_dir": config.get("data_dir", "data"),
        "port": config.get("port", 8000),
        "display_fps": display_fps,
        "display_auto_ip": display_auto_ip
    })


def update_sample_rate(logger, config, manager, data: dict):
    """Update the sample rate (1-860 Hz)."""
    sample_hz = data.get("sample_hz")
    if sample_hz < 1 or sample_hz > 860:
        raise HTTPException(status_code=400, detail="Sample rate must be between 1 and 860 Hz")

    # Update the datalogger
    if logger.set_sample_rate(sample_hz):
        _save_to_config("pika", {"sample_hz": sample_hz})

        # Broadcast the change to WebSocket clients
        import asyncio
        asyncio.create_task(manager.broadcast(json.dumps({
            "type": "config_update",
            "config": {"sample_hz": sample_hz}
        })))

        return JSONResponse({"success": True, "sample_hz": sample_hz})
    else:
        return JSONResponse({"success": False, "message": "No change needed"})


def update_adc_channel(logger, config, manager, data: dict):
    """Update the ADC channel (0-3)."""
    channel = data.get("channel")
    if channel is None or not (0 <= channel <= 3):
        raise HTTPException(status_code=400, detail="Channel must be between 0 and 3")

    if logger.set_adc_channel(channel):
        _save_to_config("pins", {"adc_channel": channel})

        # Broadcast the change to WebSocket clients
        import asyncio
        asyncio.create_task(manager.broadcast(json.dumps({
            "type": "config_update",
            "config": {"adc_channel": channel}
        })))

        return JSONResponse({"success": True, "channel": channel})
    else:
        return JSONResponse({"success": False, "message": "Failed to update channel"})
