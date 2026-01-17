"""Configuration API endpoint handlers.

Provides access to current configuration and allows updating sample rate.
"""

import json
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse


def register_api_config_routes(app: FastAPI, logger, config, manager, display_fps, display_auto_ip):
    """Register configuration API routes with the FastAPI app."""
    app.get("/api/config")(lambda: get_config(logger, config, display_fps, display_auto_ip))
    app.put("/api/config/sample-rate")(lambda sample_hz: update_sample_rate(logger, config, manager, sample_hz))


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
        "data_dir": config.get("data_dir", "data"),
        "port": config.get("port", 8000),
        "display_fps": display_fps,
        "display_auto_ip": display_auto_ip
    })


def update_sample_rate(logger, config, manager, sample_hz: int):
    """Update the sample rate (1-100 Hz).
    
    Args:
        logger: Datalogger instance
        config: Configuration dictionary
        manager: WebSocket connection manager
        sample_hz: New sample rate in Hz
        
    Returns:
        JSON response with update result
    """
    if sample_hz < 1 or sample_hz > 100:
        raise HTTPException(status_code=400, detail="Sample rate must be between 1 and 100 Hz")

    # Update the datalogger
    if logger.set_sample_rate(sample_hz):
        # Update config and save to file
        config["sample_hz"] = sample_hz
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.toml")
        try:
            import tomli_w
            with open(config_path, "wb") as f:
                tomli_w.dump({"pika": config}, f)
        except ImportError:
            # If tomli_w not available, just update in memory
            pass

        # Broadcast the change to WebSocket clients
        import asyncio
        asyncio.create_task(manager.broadcast(json.dumps({
            "type": "config_update",
            "config": {"sample_hz": sample_hz}
        })))

        return JSONResponse({"success": True, "sample_hz": sample_hz})
    else:
        return JSONResponse({"success": False, "message": "No change needed"})
