"""Streaming analysis for voltage quality (RMS, Frequency, Sags/Swells)."""
import math
import time
from collections import deque
from typing import Dict, Optional, List

class StreamAnalyzer:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.enabled_rms = self.config.get("enable_rms", True)
        self.enabled_freq = self.config.get("enable_freq", True)
        self.enabled_sags = self.config.get("enable_sags_swells", True)

        # State for RMS (1s window)
        self._window_size = 100 # Approx samples for 1s @ 100Hz, will adjust dynamic
        self._buffer = deque() 
        self._sum_v = 0.0
        self._sum_v2 = 0.0
        self._last_rms = 0.0

        # State for Frequency (Zero crossing)
        self._last_val = 0.0
        self._last_ts = 0.0
        self._crossings = deque() # timestamps of zero crossings
        self._last_freq = 60.0

        # State for Sags/Swells
        self._nominal_voltage = 120.0 # Could be configurable
        self._in_anomaly = False
        self._anomaly_start = 0.0
        self._anomalies = []

    def update_config(self, new_config: dict):
        self.config.update(new_config)
        self.enabled_rms = self.config.get("enable_rms", True)
        self.enabled_freq = self.config.get("enable_freq", True)
        self.enabled_sags = self.config.get("enable_sags_swells", True)

    def process_sample(self, ts: float, val: float) -> Dict[str, float]:
        """Process a single sample and return current metrics."""
        result = {}
        
        # Update buffer and running sums for DC offset/RMS
        # We need the buffer for both RMS and Frequency (for dynamic DC offset)
        if self.enabled_rms or self.enabled_freq:
            self._buffer.append((ts, val))
            self._sum_v += val
            self._sum_v2 += val * val
            
            # Prune old samples > 1.0s
            while len(self._buffer) > 0 and (ts - self._buffer[0][0] > 1.0):
                t_old, v_old = self._buffer.popleft()
                self._sum_v -= v_old
                self._sum_v2 -= v_old * v_old

        # 1. RMS Calculation
        if self.enabled_rms:
            # Compute RMS if we have enough data (at least a few cycles, say 100ms)
            if len(self._buffer) > 10: 
                # RMS = sqrt(mean(x^2))
                # Using running sum for O(1) calculation
                mean_sq = self._sum_v2 / len(self._buffer)
                self._last_rms = math.sqrt(max(0, mean_sq))
            
            result['rms'] = self._last_rms

        # 2. Frequency Calculation (Zero Crossing)
        if self.enabled_freq:
            # Simple zero-crossing detection (rising edge)
            # Use dynamic DC offset if we have buffer data, otherwise fallback to 1.65V
            if len(self._buffer) > 10:
                dc_offset = self._sum_v / len(self._buffer)
            else:
                dc_offset = self.config.get("dc_offset", 1.65)

            if (self._last_val <= dc_offset) and (val > dc_offset):
                # Rising edge detected
                # Use linear interpolation for more accurate crossing time
                # t_cross = t_prev + (t_curr - t_prev) * (dc_offset - v_prev) / (v_curr - v_prev)
                t_prev = self._last_ts
                v_prev = self._last_val
                
                # Check for first sample or if we have a valid previous sample
                if t_prev > 0 and val != v_prev:
                    t_cross = t_prev + (ts - t_prev) * (dc_offset - v_prev) / (val - v_prev)
                    self._crossings.append(t_cross)
                    
                    # Keep last 20 cycles
                    while len(self._crossings) > 20:
                        self._crossings.popleft()
                    
                    if len(self._crossings) > 1:
                        duration = self._crossings[-1] - self._crossings[0]
                        cycles = len(self._crossings) - 1
                        if duration > 0:
                            self._last_freq = cycles / duration
            
            self._last_ts = ts
            self._last_val = val
            result['freq'] = self._last_freq

        if self.enabled_sags:
             # Detection based on RMS
             # Nominals and thresholds should be in config, defaults provided
             nominal = self.config.get("nominal_voltage", 120.0)
             sag_thresh = self.config.get("sag_threshold", nominal * 0.9)
             swell_thresh = self.config.get("swell_threshold", nominal * 1.1)
             
             current_rms = self._last_rms
             
             status = "normal"
             if current_rms < sag_thresh:
                 status = "sag"
             elif current_rms > swell_thresh:
                 status = "swell"
                 
             if status != "normal":
                 if not self._in_anomaly:
                     self._in_anomaly = True
                     self._anomaly_start = ts
                     # Start event
             else:
                 if self._in_anomaly:
                     self._in_anomaly = False
                     # End event, log it?
                     # For now, just return status
             
             result['status'] = status
             
        return result

    def analyze_batch(self, data_points: List[tuple]) -> List[dict]:
        """Analyze a batch of historical data (ts, val)."""
        results = []
        # Reset state for batch processing to avoid carry-over artifacts
        self._buffer.clear()
        self._sum_v = 0.0
        self._sum_v2 = 0.0
        self._crossings.clear()
        self._last_rms = 0.0
        self._last_freq = 60.0
        
        for ts, val in data_points:
            metrics = self.process_sample(ts, val)
            # Only append if we have valid calculations (e.g. after buffer fills)
            # Or just append everything
            results.append({"ts": ts, **metrics})
            
        return results
