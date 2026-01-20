"""Detect voltage anomalies (brownouts, sags, swells) in incoming voltage data.

Design:
- Uses threshold-based detection (ANSI C84.1) instead of standard deviation
- Runs a background thread that periodically analyzes recent samples
- Tracks event duration (must exceed min_duration_ms to trigger)
- Provides API-friendly representation with severity levels
"""
from __future__ import annotations

import threading
import time
import json
import os
import logging
from collections import deque
from typing import List, Dict, Optional

from .voltage_convert import VoltageConverter, get_converter

logger = logging.getLogger(__name__)


class HighlightsManager:
    """Manages detection of voltage anomalies (brownouts, swells, etc.)."""
    
    def __init__(self, datalogger, data_dir='data', window_seconds=600, 
                 scan_interval=10, voltage_config=None):
        """Initialize the highlights manager.
        
        Args:
            datalogger: Datalogger instance for sample data
            data_dir: Directory for persisting highlights
            window_seconds: Analysis window in seconds
            scan_interval: Seconds between scans
            voltage_config: Voltage thresholds and calibration config
        """
        self.datalogger = datalogger
        self.data_dir = data_dir
        self.window_seconds = window_seconds
        self.scan_interval = scan_interval
        self._stop = threading.Event()
        self._thread = None
        self._highlights: List[Dict] = []
        
        # Voltage converter with thresholds
        self.voltage_config = voltage_config or {}
        self.converter = VoltageConverter(self.voltage_config)
        self.min_duration_ms = self.voltage_config.get('min_duration_ms', 50)
        
        # Buffer for streaming data (generous size for high sample rates)
        self._buffer_maxlen = 1000000 
        self._buffer = deque(maxlen=self._buffer_maxlen) 
        self._buffer_lock = threading.Lock()
        
        # Current event state
        self._current_event = None
        
        os.makedirs(self.data_dir, exist_ok=True)

    def _on_sample(self, ts, val):
        """Callback from datalogger."""
        with self._buffer_lock:
            self._buffer.append((ts, val))

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        
        # Subscribe to datalogger
        self.datalogger.add_sample_callback(self._on_sample)
        
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("HighlightsManager started (threshold-based detection, scan every %ds)" % self.scan_interval)

    def stop(self):
        self._stop.set()
        self.datalogger.remove_sample_callback(self._on_sample)
        
        if self._thread:
            self._thread.join(timeout=1.0)

    def get_highlights(self):
        return list(self._highlights)

    def _calculate_rms_ac(self, samples: List[tuple], window_ms: float = 16.67) -> List[Dict]:
        """Calculate rolling RMS values converted to AC voltage.
        
        Args:
            samples: List of (timestamp, adc_voltage) tuples
            window_ms: RMS calculation window in ms (default ~1 cycle at 60Hz)
            
        Returns:
            List of {ts, adc_rms, ac_rms} dictionaries
        """
        if len(samples) < 10:
            return []
        
        results = []
        window_s = window_ms / 1000.0
        offset = self.converter.adc_offset
        
        # Use a sliding window approach
        for i, (ts, val) in enumerate(samples):
            # Find samples within window
            window_start = ts - window_s
            window_samples = [(t, v) for t, v in samples[max(0, i-100):i+1] 
                             if t >= window_start]
            
            if len(window_samples) >= 3:
                # Calculate RMS of AC component (subtract DC offset)
                sum_sq = sum((v - offset) ** 2 for _, v in window_samples)
                adc_ac_rms = (sum_sq / len(window_samples)) ** 0.5
                
                # Convert to AC RMS voltage
                # ADC AC RMS to AC line RMS: multiply by scale factor
                ac_rms = adc_ac_rms * self.converter.adc_vpp_to_ac_rms * (2 ** 0.5)
                
                results.append({
                    'ts': ts,
                    'adc_rms': adc_ac_rms,
                    'ac_rms': ac_rms
                })
        
        return results

    def _detect_brownouts(self, samples: List[tuple]) -> List[Dict]:
        """Detect brownout events using threshold-based detection.
        
        Args:
            samples: List of (timestamp, adc_voltage) tuples
            
        Returns:
            List of event dictionaries with severity and duration
        """
        if len(samples) < 50:
            return []
        
        # Calculate RMS values
        rms_data = self._calculate_rms_ac(samples)
        if not rms_data:
            return []
        
        events = []
        current_event = None
        
        for point in rms_data:
            ts = point['ts']
            ac_rms = point['ac_rms']
            adc_rms = point['adc_rms']
            
            # Classify voltage status
            status = self.converter.classify_voltage(ac_rms)
            severity = self.converter.get_severity_level(status)
            
            if status != 'normal':
                if current_event is None:
                    # Start new event
                    current_event = {
                        'start_ts': ts,
                        'end_ts': ts,
                        'type': status,
                        'severity': severity,
                        'min_ac_v': ac_rms,
                        'max_ac_v': ac_rms,
                        'min_adc_v': adc_rms,
                        'samples': 1
                    }
                else:
                    # Continue event
                    current_event['end_ts'] = ts
                    current_event['samples'] += 1
                    current_event['min_ac_v'] = min(current_event['min_ac_v'], ac_rms)
                    current_event['max_ac_v'] = max(current_event['max_ac_v'], ac_rms)
                    current_event['min_adc_v'] = min(current_event['min_adc_v'], adc_rms)
                    
                    # Update type if severity increases
                    if severity > current_event['severity']:
                        current_event['type'] = status
                        current_event['severity'] = severity
            else:
                if current_event is not None:
                    # End event
                    duration_ms = (current_event['end_ts'] - current_event['start_ts']) * 1000
                    
                    # Only record if duration exceeds minimum
                    if duration_ms >= self.min_duration_ms:
                        current_event['duration_ms'] = duration_ms
                        events.append(current_event)
                    
                    current_event = None
        
        # Handle event that extends to end of data
        if current_event is not None:
            duration_ms = (current_event['end_ts'] - current_event['start_ts']) * 1000
            if duration_ms >= self.min_duration_ms:
                current_event['duration_ms'] = duration_ms
                events.append(current_event)
        
        # Format for API
        formatted_events = []
        for e in events:
            formatted_events.append({
                'start_ts': e['start_ts'],
                'end_ts': e['end_ts'],
                'type': e['type'],
                'severity': e['severity'],
                'duration_ms': e.get('duration_ms', 0),
                'min_voltage': round(e['min_ac_v'], 1),
                'max_voltage': round(e['max_ac_v'], 1),
                'min_adc_voltage': round(e['min_adc_v'], 4),
                'sample_count': e['samples']
            })
        
        return formatted_events

    def _run(self):
        while not self._stop.is_set():
            try:
                # Get local copy of recent buffer
                now = time.time()
                cutoff = now - self.window_seconds
                
                samples_to_analyze = []
                with self._buffer_lock:
                    # Prune old samples
                    while self._buffer and self._buffer[0][0] < cutoff:
                        self._buffer.popleft()
                    samples_to_analyze = list(self._buffer)
                
                if samples_to_analyze:
                    highlights = self._detect_brownouts(samples_to_analyze)
                    self._highlights = highlights
                    
                    try:
                        with open(os.path.join(self.data_dir, 'highlights.json'), 'w') as f:
                            json.dump(highlights, f)
                    except Exception:
                        logger.exception("Failed to write highlights.json")
            except Exception:
                logger.exception("Error running highlights detection")
            
            # Wait for next scan
            for _ in range(int(self.scan_interval)):
                if self._stop.is_set():
                    break
                time.sleep(1)


# Helper singleton
_mgr: Optional[HighlightsManager] = None


def start_highlights(datalogger, data_dir='data', voltage_config=None):
    """Start the highlights manager singleton.
    
    Args:
        datalogger: Datalogger instance
        data_dir: Data directory for persistence
        voltage_config: Optional voltage configuration
        
    Returns:
        HighlightsManager instance
    """
    global _mgr
    if _mgr is None:
        _mgr = HighlightsManager(datalogger, data_dir=data_dir, 
                                  voltage_config=voltage_config)
        _mgr.start()
    return _mgr


def stop_highlights():
    """Stop the highlights manager."""
    global _mgr
    if _mgr:
        _mgr.stop()
        _mgr = None
