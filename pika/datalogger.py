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
    def __init__(self, data_dir="data", filename_prefix="log", sample_hz=100, adc=None, retention_days=5):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.filename_prefix = filename_prefix
        self.sample_hz = sample_hz
        self.interval = 1.0 / float(self.sample_hz)
        self.adc = adc if adc is not None else (ADS1115ADC() if ADS1115ADC else MockADC())
        self._stop = threading.Event()
        self._thread = None
        self._buffer = deque(maxlen=int(self.sample_hz * 60))  # keep last 60s in memory
        self._current_date = None
        self._file = None
        self.retention_days = int(retention_days)
        # open initial file
        self._open_log_file_for_today()

    def _log_filename_for_date(self, dt):
        return os.path.join(self.data_dir, f"{self.filename_prefix}-{dt.strftime('%Y%m%d')}.csv")

    def _open_log_file_for_today(self):
        dt = time.localtime()
        today = time.strftime("%Y%m%d", dt)
        if self._current_date == today and self._file:
            return
        # close previous file
        if self._file:
            try:
                self._file.close()
            except Exception:
                logging.exception("Error closing previous log file")
            # compress previous day's file
            try:
                prev_path = self._log_filename_for_date(time.localtime(time.time() - 86400))
                if os.path.exists(prev_path) and not os.path.exists(prev_path + ".gz"):
                    import gzip, shutil
                    with open(prev_path, 'rb') as f_in, gzip.open(prev_path + '.gz', 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                    os.remove(prev_path)
            except Exception:
                logging.exception("Error compressing previous log file")
            # cleanup old logs
            try:
                self._cleanup_old_logs()
            except Exception:
                logging.exception("Error cleaning up old logs")

        self._current_date = today
        filepath = self._log_filename_for_date(time.localtime())
        new_file = not os.path.exists(filepath)
        self._file = open(filepath, "a", newline="")
        if new_file:
            writer = csv.writer(self._file)
            writer.writerow(["timestamp", "value"])
            self._file.flush()
            try:
                os.fsync(self._file.fileno())
            except Exception:
                pass

    def _cleanup_old_logs(self):
        # remove files older than retention_days (both .csv and .csv.gz)
        now = time.time()
        threshold = now - (self.retention_days * 24 * 3600)
        for fn in os.listdir(self.data_dir):
            if not (fn.startswith(self.filename_prefix + "-") and (fn.endswith('.csv') or fn.endswith('.csv.gz'))):
                continue
            path = os.path.join(self.data_dir, fn)
            try:
                mtime = os.path.getmtime(path)
                if mtime < threshold:
                    os.remove(path)
                    logging.info("Removed old log file %s", path)
            except Exception:
                logging.exception("Error removing old log file %s", path)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logging.info("Datalogger started (%.1f Hz) -> %s-YYYYMMDD.csv", self.sample_hz, self.filename_prefix)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        logging.info("Datalogger stopped")

    def _run(self):
        next_sample = time.perf_counter()
        while not self._stop.is_set():
            # ensure we have today's file
            try:
                self._open_log_file_for_today()
            except Exception:
                logging.exception("Error ensuring daily log file")

            ts = time.time()
            try:
                val = float(self.adc.read())
            except Exception as e:
                logging.exception("ADC read failed, using NaN: %s", e)
                val = float('nan')

            try:
                writer = csv.writer(self._file)
                writer.writerow(["{:.6f}".format(ts), "{:.6f}".format(val)])
                try:
                    self._file.flush()
                    os.fsync(self._file.fileno())
                except Exception:
                    pass
            except Exception:
                logging.exception("Failed to write sample to disk")

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
        # best-effort: read today's file and previous day's compressed file if needed
        today_path = self._log_filename_for_date(time.localtime())
        prev_path = self._log_filename_for_date(time.localtime(time.time() - 86400))
        paths = []
        if os.path.exists(today_path):
            paths.append(today_path)
        if os.path.exists(prev_path):
            paths.append(prev_path)
        if os.path.exists(prev_path + '.gz'):
            paths.append(prev_path + '.gz')

        lines = []
        try:
            for path in paths:
                if path.endswith('.gz'):
                    import gzip
                    with gzip.open(path, 'rt') as f:
                        reader = csv.reader(f)
                        next(reader, None)
                        for row in reader:
                            if len(row) >= 2:
                                lines.append((float(row[0]), float(row[1])))
                else:
                    with open(path, 'r') as f:
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

    def get_range(self, start_ts: float, end_ts: float, max_points: int = 1000):
        """Return downsampled data in the range [start_ts, end_ts].

        Performs streaming bucketing to produce at most `max_points` samples by averaging
        values that fall into the same time bucket. Returns a list of (ts, value) tuples.
        """
        try:
            start_ts = float(start_ts)
            end_ts = float(end_ts)
        except Exception:
            return []
        if end_ts <= start_ts:
            return []
        # determine days to check
        start_day = time.localtime(start_ts)
        end_day = time.localtime(end_ts)
        # build date list inclusive
        days = []
        dt = time.mktime(start_day)
        while dt <= end_ts:
            days.append(time.localtime(dt))
            dt += 86400
        # prepare buckets
        bucket_count = max(1, int(max_points))
        interval = (end_ts - start_ts) / bucket_count
        buckets = [{'sum': 0.0, 'count': 0, 'min': None, 'max': None, 'ts_sum': 0.0} for _ in range(bucket_count)]

        def process_file(path, open_fn):
            with open_fn(path, 'rt') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if len(row) < 2:
                        continue
                    try:
                        ts = float(row[0])
                        val = float(row[1])
                    except Exception:
                        continue
                    if ts < start_ts or ts > end_ts:
                        continue
                    idx = int((ts - start_ts) / interval)
                    if idx < 0:
                        idx = 0
                    elif idx >= bucket_count:
                        idx = bucket_count - 1
                    b = buckets[idx]
                    b['sum'] += val
                    b['count'] += 1
                    b['ts_sum'] += ts
                    if b['min'] is None or val < b['min']:
                        b['min'] = val
                    if b['max'] is None or val > b['max']:
                        b['max'] = val

        # open files for each day
        for day in days:
            path = self._log_filename_for_date(day)
            if os.path.exists(path):
                try:
                    process_file(path, open)
                except Exception:
                    logging.exception("Error processing log file %s", path)
            gz = path + '.gz'
            if os.path.exists(gz):
                try:
                    import gzip
                    process_file(gz, gzip.open)
                except Exception:
                    logging.exception("Error processing gzip log file %s", gz)

        # build result: for buckets with data, use average timestamp and mean value
        result = []
        for b in buckets:
            if b['count'] > 0:
                avg_ts = b['ts_sum'] / b['count']
                avg_val = b['sum'] / b['count']
                result.append((avg_ts, avg_val))
        return result

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
