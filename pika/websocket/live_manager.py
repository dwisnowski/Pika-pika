"""Live WebSocket connection manager.

Handles real-time data streaming for live voltage measurements.
"""

import asyncio
import json
from fastapi import WebSocket
from asyncio import Queue
from typing import List


class ConnectionManager:
    """Manages WebSocket connections for live data streaming."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.sample_queue: Queue = Queue()
        self._broadcast_task = None

    async def connect(self, websocket: WebSocket):
        """Accept and store new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection from active connections."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        """Broadcast message to all connected WebSocket clients."""
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                # Remove dead connections
                if connection in self.active_connections:
                    self.active_connections.remove(connection)

    def add_sample(self, ts: float, val: float):
        """Add a sample to the queue for broadcasting (thread-safe)."""
        try:
            # Use asyncio.create_task in a thread-safe way
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.sample_queue.put((ts, val)))
            else:
                # If no loop running, just queue it for later processing
                self.sample_queue.put_nowait((ts, val))
        except RuntimeError:
            # If no event loop, just queue it for later processing
            self.sample_queue.put_nowait((ts, val))

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
