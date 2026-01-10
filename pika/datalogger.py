"""Simple datalogger that samples an ADC at 100 Hz and writes timestamp,value to CSV.
It also keeps a short in-memory buffer for quick retrieval by the web server.

Designed to run on Raspberry Pi with ADS1115; falls back to a simulated sensor when the hardware library isn't available.
"""
from collections import deque
import csv
import os
import time
import threading
import math
import random
import logging

logging.basicConfig(level=logging.INFO)

class ADCInterface:
    def read(self):
        raise NotImplementedError

class MockADC(ADCInterface):
    def __init__(self):
        self._t0 = time.time()
    def read(self):
        t = time.time() - self._t0
        # simulated AC-ish signal + noise
        return 1.5 + math.sin(2.0 * math.pi * 1.0 * t) * 0.8 + random.uniform(-0.02, 0.02)

try:
    # Try to import Adafruit ADS1115 library (CircuitPython)
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    class ADS1115ADC(ADCInterface):
        def __init__(self, address=0x48, channel=0):
            i2c = busio.I2C(board.SCL, board.SDA)
            self.ads = ADS.ADS1115(i2c, address=address)
            self.chan = AnalogIn(self.ads, getattr(ADS, f"P{channel}"))
        def read(self):
            # return raw ADC voltage (or scaled value)
            return self.chan.voltage
except Exception:
    ADS1115ADC = None

class Datalogger:
    def __init__(self, data_dir="data", filename="log.csv", sample_hz=100, adc=None):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.filepath = os.path.join(self.data_dir, filename)
        self.sample_hz = sample_hz
        self.interval = 1.0 / float(self.sample_hz)
        self.adc = adc if adc is not None else (ADS1115ADC() if ADS1115ADC else MockADC())
        self._stop = threading.Event()
        self._thread = None
        self._buffer = deque(maxlen=int(self.sample_hz * 60))  # keep last 60s in memory
        # ensure file exists with header
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "value"])

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logging.info("Datalogger started (%.1f Hz) -> %s", self.sample_hz, self.filepath)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        logging.info("Datalogger stopped")

    def _run(self):
        # open file once and append
        with open(self.filepath, "a", newline="") as f:
            writer = csv.writer(f)
            next_sample = time.perf_counter()
            while not self._stop.is_set():
                ts = time.time()
                try:
                    val = float(self.adc.read())
                except Exception as e:
                    logging.exception("ADC read failed, using NaN: %s", e)
                    val = float('nan')
                writer.writerow(["{:.6f}".format(ts), "{:.6f}".format(val)])
                f.flush()
                os.fsync(f.fileno())
                self._buffer.append((ts, val))
                # sleep until next scheduled sample
                next_sample += self.interval
                sleep_for = next_sample - time.perf_counter()
                if sleep_for > 0:
                    time.sleep(sleep_for)
                else:
                    # we're behind schedule — skip sleeping to catch up
                    next_sample = time.perf_counter()

    def get_recent(self, seconds=5.0):
        cutoff = time.time() - float(seconds)
        return [(ts, val) for ts, val in list(self._buffer) if ts >= cutoff]

    def tail_from_disk(self, seconds=10.0, max_lines=10000):
        """Fill buffer from disk by reading last lines up to `seconds` window (best effort)."""
        if not os.path.exists(self.filepath):
            return
        lines = []
        try:
            with open(self.filepath, "r") as f:
                # naive approach: read all but skip header if large files not expected
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if len(row) >= 2:
                        lines.append((float(row[0]), float(row[1])))
            cutoff = time.time() - seconds
            for ts, val in lines:
                if ts >= cutoff:
                    self._buffer.append((ts, val))
        except Exception:
            logging.exception("Failed to tail from disk.")
