"""Detect anomalies (highlights) in the incoming voltage data and expose them for the web UI.

Design:
- Runs a background thread that periodically analyzes recent samples (by default last 10 minutes).
- Uses a rolling-window (Welford) estimate of mean & variance; flags points exceeding thresholds.
- Writes results to an in-memory list and optionally to `data/highlights.json` for persistence.
- Provides a small API-friendly representation: list of {start_ts, end_ts, peak_ts, peak_value, score}.
"""
from __future__ import annotations

import threading
import time
import json
import os
import logging
from collections import deque
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class HighlightsManager:
    def __init__(self, datalogger, data_dir='data', window_seconds=600, scan_interval=60, min_points=50):
        self.datalogger = datalogger
        self.data_dir = data_dir
        self.window_seconds = window_seconds
        self.scan_interval = scan_interval
        self.min_points = min_points
        self._stop = threading.Event()
        self._thread = None
        self._highlights: List[Dict] = []
        
        # Internal buffer for streaming data (approx 10-15 mins to be safe)
        # Assuming max 860Hz * 600s = 516,000 points. 
        # Deque is efficient for append/popleft.
        # We need to know sample rate to size it? Or just strict time-based pruning?
        # Let's use time-based pruning in the scan loop, and a generous maxlen.
        self._buffer_maxlen = 1000000 
        self._buffer = deque(maxlen=self._buffer_maxlen) 
        self._buffer_lock = threading.Lock()
        
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
        logger.info("HighlightsManager started (scan every %ds, streaming mode)" % self.scan_interval)

    def stop(self):
        self._stop.set()
        # Unsubscribe
        self.datalogger.remove_sample_callback(self._on_sample)
        
        if self._thread:
            self._thread.join(timeout=1.0)

    def get_highlights(self):
        return list(self._highlights)

    def _detect(self, samples: List[tuple]) -> List[Dict]:
        if len(samples) < self.min_points:
            return []
        
        # simple global stats
        vals = [v for (_, v) in samples]
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        std = var ** 0.5
        thresh = max(0.06, 3.0 * std)

        highlights = []
        current = None
        for ts, v in samples:
            if abs(v - mean) > thresh:
                if current is None:
                    current = {"start": ts, "end": ts, "peak_ts": ts, "peak_val": v, "count": 1}
                else:
                    current["end"] = ts
                    current["count"] += 1
                    if abs(v) > abs(current["peak_val"]):
                        current["peak_val"] = v
                        current["peak_ts"] = ts
            else:
                if current is not None:
                    highlights.append(current)
                    current = None
        if current is not None:
            highlights.append(current)

        out = []
        for h in highlights:
            duration = h['end'] - h['start']
            score = h['count'] * (abs(h['peak_val'] - mean))
            out.append({
                'start_ts': h['start'],
                'end_ts': h['end'],
                'peak_ts': h['peak_ts'],
                'peak_value': h['peak_val'],
                'duration': duration,
                'score': score
            })
        return out

    def _run(self):
        while not self._stop.is_set():
            try:
                # Get local copy of recent buffer
                now = time.time()
                cutoff = now - self.window_seconds
                
                samples_to_analyze = []
                with self._buffer_lock:
                    # Prune old
                    while self._buffer and self._buffer[0][0] < cutoff:
                        self._buffer.popleft()
                    # Copy reference (list conversion is fast enough for <1M items)
                    # Optimization: iterate directly to avoid full copy if massive?
                    # For now, list(deque) is simplest.
                    samples_to_analyze = list(self._buffer)
                
                if samples_to_analyze:
                    # Sort not needed if append is monotonic, but safety first
                    # samples_to_analyze.sort() 
                    highlights = self._detect(samples_to_analyze)
                    self._highlights = highlights
                    
                    try:
                        with open(os.path.join(self.data_dir, 'highlights.json'), 'w') as f:
                            json.dump(highlights, f)
                    except Exception:
                        logger.exception("Failed to write highlights.json")
            except Exception:
                logger.exception("Error running highlights detection")
            
            # sleep
            for _ in range(int(self.scan_interval)):
                if self._stop.is_set():
                    break
                time.sleep(1)

# helper singleton
_mgr: Optional[HighlightsManager] = None

def start_highlights(datalogger, data_dir='data'):
    global _mgr
    if _mgr is None:
        _mgr = HighlightsManager(datalogger, data_dir=data_dir)
        _mgr.start()
    return _mgr

def stop_highlights():
    global _mgr
    if _mgr:
        _mgr.stop()
        _mgr = None
