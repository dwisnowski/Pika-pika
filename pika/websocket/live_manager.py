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
    
    def __init__(self, batch_mode=True, batch_interval_ms=50):
        self.active_connections: List[WebSocket] = []
        self.sample_queue: Queue = Queue()
        self._broadcast_task = None
        self.batch_mode = batch_mode
        self.batch_interval_ms = batch_interval_ms
        self.batch_buffer = []  # Buffer for batched samples

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

    def add_sample(self, ts: float, val: float, analysis=None):
        """Add a sample and optional analysis to the queue for broadcasting (thread-safe)."""
        try:
            # Use asyncio.create_task in a thread-safe way
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.sample_queue.put((ts, val, analysis)))
            else:
                # If no loop running, just queue it for later processing
                self.sample_queue.put_nowait((ts, val, analysis))
        except RuntimeError:
            # If no event loop, just queue it for later processing
            self.sample_queue.put_nowait((ts, val, analysis))

    async def start_broadcast_task(self):
        """Start the background task that broadcasts samples to WebSocket clients."""
        if self._broadcast_task is None:
            self._broadcast_task = asyncio.create_task(self._broadcast_samples())

    async def _broadcast_samples(self):
        """Background task that processes the sample queue and broadcasts to clients."""
        if self.batch_mode:
            await self._broadcast_batched()
        else:
            await self._broadcast_individual()

    async def _broadcast_individual(self):
        """Original mode: broadcast each sample immediately."""
        while True:
            try:
                ts, val, analysis = await self.sample_queue.get()
                data_msg = {
                    "type": "new_sample",
                    "data": [ts, val]
                }
                if analysis:
                    data_msg["analysis"] = analysis
                
                await self.broadcast(json.dumps(data_msg))
                self.sample_queue.task_done()
            except Exception as e:
                print(f"Error broadcasting sample: {e}")
                await asyncio.sleep(0.1)

    async def _broadcast_batched(self):
        """Batch mode: collect samples and broadcast in batches at regular intervals."""
        import time
        last_broadcast = time.time()
        last_analysis = None
        
        while True:
            try:
                # Collect samples from queue with timeout
                try:
                    ts, val, analysis = await asyncio.wait_for(
                        self.sample_queue.get(), 
                        timeout=self.batch_interval_ms / 1000.0
                    )
                    self.batch_buffer.append([ts, val])
                    if analysis:
                        last_analysis = analysis
                    self.sample_queue.task_done()
                except asyncio.TimeoutError:
                    pass  # No samples in queue, proceed to broadcast
                
                # Check if it's time to broadcast
                now = time.time()
                if (now - last_broadcast) >= (self.batch_interval_ms / 1000.0):
                    if self.batch_buffer:
                        data_msg = {
                            "type": "batch_samples",
                            "data": self.batch_buffer[:]
                        }
                        if last_analysis:
                            data_msg["analysis"] = last_analysis
                        
                        await self.broadcast(json.dumps(data_msg))
                        self.batch_buffer.clear()
                        last_analysis = None
                    last_broadcast = now
                    
            except Exception as e:
                print(f"Error broadcasting batch: {e}")
                await asyncio.sleep(0.1)
