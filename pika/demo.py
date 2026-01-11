"""Demo data generator for mocked voltage data and highlights.

Provides functions used by demo endpoints to simulate a voltage signal with occasional anomalies.
"""
from __future__ import annotations

import math
import random
import time
from typing import List, Tuple, Dict

SAMPLE_HZ = 100

# Define a few demo anomalies relative to current time (seconds ago)
# Each entry: (seconds_ago_center, duration_sec, magnitude, type)
# type: 'spike' for positive magnitude, 'drop' for negative magnitude
DEMO_ANOMALIES = [
    (30 * 60, 6, 1.2, 'spike'),    # 30 minutes ago, 6s spike
    (90 * 60, 10, -1.0, 'drop'),   # 90 minutes ago, 10s drop
    (10 * 60, 3, 0.8, 'spike'),    # 10 minutes ago, 3s spike
    (5 * 60, 4, -0.6, 'drop'),     # 5 minutes ago, 4s drop
]


def _base_signal(ts: float) -> float:
    # Consistent voltage around 1.5V with small random noise (no sine wave)
    return 1.5 + (random.random() - 0.5) * 0.01  # Very small noise, ~1.5V ± 0.005V


def generate_samples(start_ts: float, end_ts: float, sample_hz: int = SAMPLE_HZ, inject_anomalies: bool = True) -> List[Tuple[float, float]]:
    """Generate samples between start_ts and end_ts (epoch seconds).

    Returns a list of (ts, value).
    """
    # limit the number of points we actually generate for very large ranges
    max_points = int(max(1, (end_ts - start_ts) * min(sample_hz, SAMPLE_HZ)))
    result: List[Tuple[float, float]] = []
    dt = 1.0 / float(sample_hz)
    t = start_ts
    # create anomaly definitions based on now
    now = time.time()
    anomalies: List[Dict] = []
    if inject_anomalies:
        for sec_ago_center, dur, mag, anom_type in DEMO_ANOMALIES:
            center = now - sec_ago_center
            anomalies.append({
                'start': center - dur / 2.0, 
                'end': center + dur / 2.0, 
                'mag': mag,
                'type': anom_type
            })
    while t <= end_ts:
        v = _base_signal(t)
        # apply anomalies
        if inject_anomalies:
            for a in anomalies:
                if a['start'] <= t <= a['end']:
                    # ramp up/down with a simple envelope
                    span = a['end'] - a['start']
                    mid = (a['start'] + a['end']) / 2.0
                    env = 1.0 - abs((t - mid) / (span / 2.0))
                    v += a['mag'] * env
        result.append((t, v))
        t += dt
    return result


def downsample_points(points: List[Tuple[float, float]], max_points: int) -> List[Tuple[float, float]]:
    """Downsample by bucketing to at most max_points, using average per bucket."""
    if not points or len(points) <= max_points:
        return points
    start = points[0][0]
    end = points[-1][0]
    interval = (end - start) / float(max_points)
    buckets = []
    cur_bucket = {'sum': 0.0, 'count': 0, 'ts_sum': 0.0}
    bi = 0
    result: List[Tuple[float, float]] = []
    for ts, v in points:
        bi = int((ts - start) / interval)
        if bi >= max_points:
            bi = max_points - 1
        # simple mapping by index: when bi changes, flush bucket
        if not buckets:
            # initialize list of buckets lazily
            buckets = [{'sum':0.0,'count':0,'ts_sum':0.0} for _ in range(max_points)]
        b = buckets[bi]
        b['sum'] += v
        b['count'] += 1
        b['ts_sum'] += ts
    for b in buckets:
        if b['count'] > 0:
            result.append((b['ts_sum'] / b['count'], b['sum'] / b['count']))
    return result


def highlights_for_range(start_ts: float, end_ts: float) -> List[Dict]:
    """Return highlight summaries for anomalies that intersect the requested range."""
    now = time.time()
    anomalies: List[Dict] = []
    for sec_ago_center, dur, mag, anom_type in DEMO_ANOMALIES:
        center = now - sec_ago_center
        a_start = center - dur / 2.0
        a_end = center + dur / 2.0
        if (a_end >= start_ts and a_start <= end_ts):
            peak_ts = center
            anomalies.append({
                'start_ts': a_start,
                'end_ts': a_end,
                'peak_ts': peak_ts,
                'peak_value': 1.5 + mag,  # approximate
                'duration': dur,
                'score': abs(mag) * dur,
                'type': anom_type  # 'spike' or 'drop'
            })
    return anomalies

# Convenience helpers used by endpoints

def recent(seconds: float = 5.0, max_points: int = 1000):
    end = time.time()
    start = end - float(seconds)
    pts = generate_samples(start, end)
    # cap points
    if len(pts) > max_points:
        pts = downsample_points(pts, max_points)
    return pts


def range_query(start: float, end: float, max_points: int = 1000):
    # generate direct but sample at coarser rate if needed
    total_seconds = max(1.0, end - start)
    max_raw = int(total_seconds * SAMPLE_HZ)
    if max_raw <= max_points:
        pts = generate_samples(start, end)
        return pts
    # else pick an effective sample rate that will produce ~max_points
    effective_hz = max(1, int(max_points / total_seconds))
    # step through at effective_hz
    dt = 1.0 / effective_hz
    t = start
    pts = []
    while t <= end:
        # sample the base signal (and anomalies) at t
        v = _base_signal(t)
        now = time.time()
        # apply anomalies as in generate_samples
        for sec_ago_center, dur, mag, anom_type in DEMO_ANOMALIES:
            center = now - sec_ago_center
            a_start = center - dur / 2.0
            a_end = center + dur / 2.0
            if a_start <= t <= a_end:
                span = a_end - a_start
                mid = (a_start + a_end) / 2.0
                env = 1.0 - abs((t - mid) / (span / 2.0))
                v += mag * env
        pts.append((t, v))
        t += dt
    return pts
