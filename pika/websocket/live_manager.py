"""Live WebSocket connection manager.

Handles real-time data streaming for live voltage measurements.
"""

import asyncio
import json
import time
from fastapi import WebSocket
from asyncio import Queue
from typing import List, Optional
from ..shared_memory import SharedSampleBuffer, SharedAnalysisBuffer


class ConnectionManager:
    """Manages WebSocket connections for live data streaming."""
    
    def __init__(self, sample_buffer: Optional[SharedSampleBuffer] = None, 
                 analysis_buffer: Optional[SharedAnalysisBuffer] = None):
        self.active_connections: List[WebSocket] = []
        self.sample_queue: Queue = Queue()
        self._broadcast_task = None
        self.sample_buffer = sample_buffer
        self.analysis_buffer = analysis_buffer
        self._last_sample_time = 0.0
        self._last_analysis_time = 0.0
        self._cached_data = []  # Cache for graceful degradation

    async def connect(self, websocket: WebSocket):
        """Accept and store new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        
        # Send initial data from shared memory if available
        await self._send_initial_data(websocket)

    async def _send_initial_data(self, websocket: WebSocket):
        """Send last 5 seconds of data to new WebSocket connection."""
        try:
            recent_data = []
            
            if self.sample_buffer:
                # Get recent data from shared memory (exactly 5 seconds as per requirements)
                recent_data = self.sample_buffer.read_recent(5.0)
            
            # Fallback to cached data if shared memory unavailable or empty
            if not recent_data and self._cached_data:
                cutoff = time.time() - 5.0
                recent_data = [(ts, val) for ts, val in self._cached_data if ts >= cutoff]
            
            # Send recent data if available
            if recent_data:
                data_msg = {
                    "type": "recent_data",
                    "data": [[ts, val] for ts, val in recent_data],
                    "count": len(recent_data),
                    "timespan": 5.0
                }
                await websocket.send_text(json.dumps(data_msg))
            else:
                # Send empty data message to indicate no data available
                empty_msg = {
                    "type": "recent_data",
                    "data": [],
                    "count": 0,
                    "timespan": 5.0,
                    "message": "No recent data available"
                }
                await websocket.send_text(json.dumps(empty_msg))
                
            # Also send current analysis if available
            if self.analysis_buffer:
                try:
                    analysis_data = self.analysis_buffer.get_current_analysis()
                    if analysis_data.get('last_updated', 0) > 0:
                        analysis_msg = {
                            "type": "initial_analysis",
                            "analysis": {
                                'rms': analysis_data.get('rms', 0.0),
                                'frequency': analysis_data.get('frequency', 60.0),
                                'sags_swells': analysis_data.get('sags_swells', [])
                            }
                        }
                        await websocket.send_text(json.dumps(analysis_msg))
                except Exception as e:
                    print(f"Error sending initial analysis: {e}")
                    
        except Exception as e:
            # Don't fail connection if initial data send fails
            print(f"Error sending initial data: {e}")
            
            # Send error message to client for debugging
            try:
                error_msg = {
                    "type": "initial_data_error",
                    "error": str(e),
                    "message": "Failed to load initial data"
                }
                await websocket.send_text(json.dumps(error_msg))
            except Exception:
                pass  # If we can't even send error message, just continue

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
        """Add a sample and optional analysis to the queue for broadcasting (thread-safe).
        
        This method is kept for backward compatibility but is deprecated.
        The ConnectionManager now reads directly from shared memory.
        """
        try:
            # Cache data for graceful degradation
            self._cached_data.append((ts, val))
            # Keep only last 60 seconds of cached data
            cutoff = time.time() - 60.0
            self._cached_data = [(t, v) for t, v in self._cached_data if t >= cutoff]
            
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
            self._broadcast_task = asyncio.create_task(self._broadcast_from_shared_memory())

    async def _broadcast_from_shared_memory(self):
        """Background task that reads from shared memory and broadcasts to clients."""
        while True:
            try:
                # Check for new samples in shared memory
                await self._check_and_broadcast_samples()
                
                # Check for new analysis data (at 5Hz as per requirements)
                await self._check_and_broadcast_analysis()
                
                # Small sleep to avoid busy waiting
                await asyncio.sleep(0.01)  # 100Hz check rate
                
            except Exception as e:
                print(f"Error in shared memory broadcast: {e}")
                await asyncio.sleep(0.1)

    async def _check_and_broadcast_samples(self):
        """Check for new samples and broadcast them."""
        if not self.sample_buffer:
            # Graceful degradation: use cached data if available
            await self._broadcast_cached_data()
            return
            
        try:
            # Get the latest sample
            latest_sample = self.sample_buffer.get_latest_sample()
            if not latest_sample:
                # No samples available, try cached data
                await self._broadcast_cached_data()
                return
                
            ts, val = latest_sample
            
            # Only broadcast if this is a new sample
            if ts > self._last_sample_time:
                self._last_sample_time = ts
                
                # Update cached data for fallback
                self._cached_data.append((ts, val))
                # Keep only last 60 seconds of cached data
                cutoff = time.time() - 60.0
                self._cached_data = [(t, v) for t, v in self._cached_data if t >= cutoff]
                
                # Get current analysis if available
                analysis = None
                if self.analysis_buffer:
                    analysis_data = self.analysis_buffer.get_current_analysis()
                    if analysis_data.get('last_updated', 0) > 0:
                        analysis = {
                            'rms': analysis_data.get('rms', 0.0),
                            'frequency': analysis_data.get('frequency', 60.0),
                            'sags_swells': analysis_data.get('sags_swells', [])
                        }
                
                data_msg = {
                    "type": "new_sample",
                    "data": [ts, val]
                }
                if analysis:
                    data_msg["analysis"] = analysis
                
                await self.broadcast(json.dumps(data_msg))
                
        except Exception as e:
            print(f"Error checking samples: {e}")
            # Fallback to cached data on error
            await self._broadcast_cached_data()

    async def _broadcast_cached_data(self):
        """Broadcast cached data when shared memory is unavailable."""
        if not self._cached_data:
            return
            
        try:
            # Get the most recent cached sample
            latest_cached = self._cached_data[-1]
            ts, val = latest_cached
            
            # Only broadcast if this is newer than last broadcast
            if ts > self._last_sample_time:
                self._last_sample_time = ts
                
                data_msg = {
                    "type": "new_sample",
                    "data": [ts, val],
                    "source": "cached"  # Indicate this is cached data
                }
                
                await self.broadcast(json.dumps(data_msg))
                
        except Exception as e:
            print(f"Error broadcasting cached data: {e}")

    async def _check_and_broadcast_analysis(self):
        """Check for updated analysis data and broadcast at 5Hz."""
        if not self.analysis_buffer:
            # Graceful degradation: send default analysis if no buffer available
            await self._broadcast_default_analysis()
            return
            
        try:
            current_time = time.time()
            
            # Only check analysis every 200ms (5Hz)
            if current_time - self._last_analysis_time < 0.2:
                return
                
            analysis_data = self.analysis_buffer.get_current_analysis()
            last_updated = analysis_data.get('last_updated', 0)
            
            # Check if analysis buffer is fresh (updated within last 10 seconds)
            if not self.analysis_buffer.is_data_fresh(10.0):
                await self._broadcast_default_analysis()
                return
            
            # Only broadcast if analysis data has been updated
            if last_updated > self._last_analysis_time:
                self._last_analysis_time = current_time
                
                analysis_msg = {
                    "type": "analysis_update",
                    "analysis": {
                        'rms': analysis_data.get('rms', 0.0),
                        'frequency': analysis_data.get('frequency', 60.0),
                        'sags_swells': analysis_data.get('sags_swells', [])
                    }
                }
                
                await self.broadcast(json.dumps(analysis_msg))
                
        except Exception as e:
            print(f"Error checking analysis: {e}")
            # Fallback to default analysis on error
            await self._broadcast_default_analysis()

    async def _broadcast_default_analysis(self):
        """Broadcast default analysis when analysis buffer is unavailable."""
        current_time = time.time()
        
        # Only broadcast every 5 seconds to avoid spam
        if current_time - self._last_analysis_time < 5.0:
            return
            
        self._last_analysis_time = current_time
        
        try:
            analysis_msg = {
                "type": "analysis_update",
                "analysis": {
                    'rms': 0.0,
                    'frequency': 60.0,
                    'sags_swells': []
                },
                "source": "default"  # Indicate this is default data
            }
            
            await self.broadcast(json.dumps(analysis_msg))
            
        except Exception as e:
            print(f"Error broadcasting default analysis: {e}")

    async def _broadcast_samples(self):
        """Background task that processes the sample queue and broadcasts to clients.
        
        This method is kept for backward compatibility but is deprecated.
        Use _broadcast_from_shared_memory instead.
        """
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

    def is_datalogger_available(self) -> bool:
        """Check if datalogger is available by testing shared memory access."""
        if not self.sample_buffer:
            return False
            
        try:
            # Try to get buffer info to test if shared memory is accessible
            info = self.sample_buffer.get_buffer_info()
            # Consider datalogger available if we have recent data or buffer has samples
            has_recent_data = time.time() - self._last_sample_time < 10.0
            has_buffer_data = info.get('count', 0) > 0
            return has_recent_data or has_buffer_data
        except Exception:
            return False

    def get_recent_data(self, seconds: float = 5.0) -> list:
        """Get recent data for API endpoints (maintains compatibility)."""
        try:
            if self.sample_buffer:
                return self.sample_buffer.read_recent(seconds)
            elif self._cached_data:
                cutoff = time.time() - seconds
                return [(ts, val) for ts, val in self._cached_data if ts >= cutoff]
            else:
                return []
        except Exception as e:
            print(f"Error getting recent data: {e}")
            return []

    def get_current_analysis(self) -> dict:
        """Get current analysis data for API endpoints (maintains compatibility)."""
        try:
            if self.analysis_buffer:
                return self.analysis_buffer.get_current_analysis()
            else:
                return {
                    'rms': 0.0,
                    'frequency': 60.0,
                    'sags_swells': [],
                    'last_updated': 0.0
                }
        except Exception as e:
            print(f"Error getting analysis data: {e}")
            return {
                'rms': 0.0,
                'frequency': 60.0,
                'sags_swells': [],
                'last_updated': 0.0,
                'error': str(e)
            }

    def get_connection_status(self) -> dict:
        """Get current connection status for client information."""
        datalogger_available = self.is_datalogger_available()
        
        status = {
            'datalogger_available': datalogger_available,
            'active_connections': len(self.active_connections),
            'last_sample_time': self._last_sample_time,
            'last_analysis_time': self._last_analysis_time,
            'cached_data_points': len(self._cached_data)
        }
        
        # Add buffer information if available
        if self.sample_buffer:
            try:
                buffer_info = self.sample_buffer.get_buffer_info()
                status['sample_buffer'] = {
                    'count': buffer_info.get('count', 0),
                    'utilization': buffer_info.get('utilization', 0.0)
                }
            except Exception:
                status['sample_buffer'] = {'error': 'Unable to access sample buffer'}
        
        if self.analysis_buffer:
            try:
                analysis_info = self.analysis_buffer.get_buffer_info()
                status['analysis_buffer'] = {
                    'is_fresh': analysis_info.get('is_fresh', False),
                    'last_update': analysis_info.get('last_update', 0.0)
                }
            except Exception:
                status['analysis_buffer'] = {'error': 'Unable to access analysis buffer'}
        
        # Add degradation mode indicator
        if not datalogger_available:
            status['mode'] = 'degraded'
            status['message'] = 'Using cached data - datalogger unavailable'
        else:
            status['mode'] = 'normal'
            
        return status
