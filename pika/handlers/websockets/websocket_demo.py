"""Demo WebSocket endpoint handler.

Handles real-time demo data streaming for testing without hardware.
"""

import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect


def register_websocket_demo_routes(app: FastAPI, demo_manager):
    """Register demo WebSocket routes with the FastAPI app."""
    
    @app.websocket("/ws/demo")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket_demo(websocket, demo_manager)


async def websocket_demo(websocket: WebSocket, demo_manager):
    """WebSocket endpoint for real-time demo data streaming.
    
    Args:
        websocket: WebSocket connection
        demo_manager: Demo connection manager instance
    """
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
