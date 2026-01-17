"""Demo WebSocket connection manager.

Handles real-time demo data streaming for testing without hardware.
"""

import asyncio
import json
import time
import os
import csv
from fastapi import WebSocket
from typing import List


class DemoConnectionManager:
    """Manages WebSocket connections for demo data streaming and simulation."""
    
    def __init__(self, data_dir: str = "data"):
        self.active_connections: List[WebSocket] = []
        self._demo_task = None
        self._pending_anomalies = asyncio.Queue()
        self.data_dir = data_dir
        self.demo_csv_path = os.path.join(data_dir, "demo.csv")
        self.demo_highlights_path = os.path.join(data_dir, "demo_highlights.json")

    async def connect(self, websocket: WebSocket):
        """Accept and store new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        if not self._demo_task:
            self._demo_task = asyncio.create_task(self._run_demo_simulation())

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection from active connections."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if not self.active_connections:
            if self._demo_task:
                self._demo_task.cancel()
                self._demo_task = None

    async def broadcast(self, message: str):
        """Broadcast message to all connected WebSocket clients."""
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                # Remove dead connections
                if connection in self.active_connections:
                    self.active_connections.remove(connection)

    async def _run_demo_simulation(self):
        """Simulate real-time demo data by generating consistent voltage with occasional anomalies."""
        import random
        
        # Import demo module for data generation
        from .. import demo
        
        # Ensure demo.csv has a header if it's new
        if not os.path.exists(self.demo_csv_path):
            os.makedirs(os.path.dirname(self.demo_csv_path), exist_ok=True)
            with open(self.demo_csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "value"])

        # Track active anomalies for real-time generation
        active_anomalies = []  # List of (end_time, magnitude, type, start_time, center)
        next_anomaly_time = None
        anomaly_counter = 0

        # Send initial data
        now = time.time()
        initial_points = demo.recent(seconds=5.0, max_points=500)
        if initial_points:
            data_msg = {
                "type": "recent_data",
                "data": [[ts, val] for ts, val in initial_points]
            }
            await self.broadcast(json.dumps(data_msg))

        # Send initial highlights
        highlights = demo.highlights_for_range(now - 3600, now)
        highlights_msg = {
            "type": "highlights",
            "highlights": highlights
        }
        await self.broadcast(json.dumps(highlights_msg))
        
        # Save initial highlights to file
        with open(self.demo_highlights_path, 'w') as f:
            json.dump(highlights, f)

        # Simulate real-time data
        sample_count = 0
        base_voltage = 1.5
        while self.active_connections:
            try:
                t = time.time()
                
                # Remove expired anomalies
                active_anomalies = [a for a in active_anomalies if a[0] > t]
                
                # Occasionally trigger a new anomaly (every 15-45 seconds randomly)
                if next_anomaly_time is None:
                    # Schedule next anomaly in 15-45 seconds
                    next_anomaly_time = t + random.uniform(15, 45)
                elif t >= next_anomaly_time:
                    # Trigger a new anomaly
                    anomaly_counter += 1
                    duration = random.uniform(2, 8)  # 2-8 seconds
                    is_spike = random.random() > 0.4  # 60% chance spike, 40% drop
                    
                    if is_spike:
                        magnitude = random.uniform(0.6, 1.5)  # Positive spike
                        anom_type = 'spike'
                    else:
                        magnitude = random.uniform(-1.2, -0.5)  # Negative drop
                        anom_type = 'drop'
                    
                    center = t
                    start_time = center - duration / 2.0
                    end_time = center + duration / 2.0
                    
                    active_anomalies.append((end_time, magnitude, anom_type, start_time, center))
                    next_anomaly_time = None  # Schedule next one
                
                # Generate consistent base voltage with small noise
                voltage = base_voltage + random.uniform(-0.005, 0.005)
                
                # Check for pending manual anomalies
                try:
                    while not self._pending_anomalies.empty():
                        manual_anom = self._pending_anomalies.get_nowait()
                        duration = random.uniform(3, 10)
                        magnitude = random.uniform(1.0, 1.8) if manual_anom.get('type') == 'spike' else random.uniform(-1.5, -0.8)
                        anom_type = manual_anom.get('type', 'spike')
                        
                        center = t
                        start_time = center - duration / 2.0
                        end_time = center + duration / 2.0
                        
                        active_anomalies.append((end_time, magnitude, anom_type, start_time, center))
                except asyncio.QueueEmpty:
                    pass

                # Apply active anomalies
                for end_time, magnitude, anom_type, start_time, center in active_anomalies:
                    if start_time <= t <= end_time:
                        # Calculate envelope (bell curve shape)
                        span = end_time - start_time
                        env = 1.0 - abs((t - center) / (span / 2.0))
                        voltage += magnitude * env

                # Save to demo.csv
                with open(self.demo_csv_path, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["{:.6f}".format(t), "{:.6f}".format(voltage)])

                # Send new sample
                sample_msg = {
                    "type": "new_sample",
                    "data": [t, voltage]
                }
                await self.broadcast(json.dumps(sample_msg))

                # Occasionally update highlights (including new anomalies)
                sample_count += 1
                if sample_count % 100 == 0:  # Every ~10 seconds at 10Hz simulation
                    highlights = demo.highlights_for_range(t - 3600, t)
                    
                    # Add any recently triggered real-time anomalies to highlights
                    for end_time, magnitude, anom_type, start_time, center in active_anomalies:
                        if start_time >= t - 3600:  # Within last hour
                            highlights.append({
                                'start_ts': start_time,
                                'end_ts': end_time,
                                'peak_ts': center,
                                'peak_value': base_voltage + magnitude,
                                'duration': end_time - start_time,
                                'score': abs(magnitude) * (end_time - start_time),
                                'type': anom_type
                            })
                    
                    # Save highlights to file
                    with open(self.demo_highlights_path, 'w') as f:
                        json.dump(highlights, f)

                    highlights_msg = {
                        "type": "highlights",
                        "highlights": highlights
                    }
                    await self.broadcast(json.dumps(highlights_msg))

                await asyncio.sleep(0.1)  # 10Hz simulation

            except Exception as e:
                print(f"Demo simulation error: {e}")
                await asyncio.sleep(1.0)

    def trigger_anomaly(self, anomaly_type: str = 'spike'):
        """Trigger a manual anomaly in the demo simulation."""
        self._pending_anomalies.put_nowait({'type': anomaly_type})
