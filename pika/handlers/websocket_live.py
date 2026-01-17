"""Live WebSocket endpoint handler.

Handles real-time data streaming for live voltage measurements.
"""

import asyncio
import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect


def register_websocket_live_routes(app: FastAPI, manager, logger, app_state, data_dir):
    """Register live WebSocket routes with the FastAPI app."""
    
    @app.websocket("/ws/live")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket_live(websocket, manager, logger, app_state, data_dir)


async def websocket_live(websocket: WebSocket, manager, logger, app_state, data_dir):
    """WebSocket endpoint for real-time live data streaming.
    
    Args:
        websocket: WebSocket connection
        manager: Connection manager for live data
        logger: Datalogger instance
        app_state: FastAPI application state
        data_dir: Data directory path
    """
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
            hl = getattr(app_state, '_highlights', None)
            highlights = []
            if hl is not None:
                highlights = hl.get_highlights()
            else:
                # fallback: try reading from disk
                path = f"{data_dir}/highlights.json"
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        highlights = json.load(f)

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
