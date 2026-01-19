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
        
        # 1. RMS Calculation
        if self.enabled_rms:
            # Keep ~1 second of data. 
            # We don't know exact sample rate, so we use timestamp to prune.
            self._buffer.append((ts, val))
            
            # Prune old samples > 1.0s
            while len(self._buffer) > 0 and (ts - self._buffer[0][0] > 1.0):
                self._buffer.popleft()
            
            # Compute RMS if we have enough data (at least a few cycles, say 100ms)
            if len(self._buffer) > 10: 
                # RMS = sqrt(mean(x^2))
                # Optimization: Could maintain running sum_sq, but strict moving window is safer against drift
                sum_sq = sum(v*v for t, v in self._buffer)
                mean_sq = sum_sq / len(self._buffer)
                self._last_rms = math.sqrt(mean_sq)
            
            result['rms'] = self._last_rms

        # 2. Frequency Calculation (Zero Crossing)
        if self.enabled_freq:
            # Simple zero-crossing detection (rising edge)
            # We assume signal is roughly centered or use DC offset removal
            if self.enabled_rms and len(self._buffer) > 10:
                dc_offset = sum(v for t, v in self._buffer) / len(self._buffer)
            else:
                dc_offset = 1.65 # Default center for 3.3V ADC

            if (self._last_val <= dc_offset) and (val > dc_offset):
                # Rising edge
                self._crossings.append(ts)
                # Keep last 10-20 cycles (approx 0.3s)
                while len(self._crossings) > 20:
                    self._crossings.popleft()
                
                if len(self._crossings) > 1:
                    # Duration for N cycles
                    duration = self._crossings[-1] - self._crossings[0]
                    cycles = len(self._crossings) - 1
                    if duration > 0:
                        self._last_freq = cycles / duration
            
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
        self._crossings.clear()
        self._last_rms = 0.0
        self._last_freq = 60.0
        
        for ts, val in data_points:
            metrics = self.process_sample(ts, val)
            # Only append if we have valid calculations (e.g. after buffer fills)
            # Or just append everything
            results.append({"ts": ts, **metrics})
            
        return results
