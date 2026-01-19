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
        logging.info("Using MockADC (simulated data)")
        self._t0 = time.time()
    def read(self):
        t = time.time() - self._t0
        # simulated AC-ish signal + noise
        return 10 #1.5 + math.sin(2.0 * math.pi * 1.0 * t) * 0.8 + random.uniform(-0.02, 0.02)

try:
    # Try to import Adafruit ADS1115 library (CircuitPython)
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    from adafruit_ads1x15 import ads1x15
    class ADS1115ADC(ADCInterface):
        def __init__(self, address=0x48, channel=0, target_rate=100):
            logging.info("Using ADS1115 ADC at address 0x%02X, channel %d. Target Rate: %d", address, channel, target_rate)
            i2c = busio.I2C(board.SCL, board.SDA)
            self.ads = ADS.ADS1115(i2c, address=address)
            self.set_rate(target_rate)
            self.chan = AnalogIn(self.ads, getattr(ads1x15.Pin, f"A{channel}"))

        def set_rate(self, target_rate):
            """Set the ADS1115 data rate to the smallest valid value >= target_rate."""
            rates = [8, 16, 32, 64, 128, 250, 475, 860]
            selected_rate = 860
            for r in rates:
                if r >= target_rate:
                    selected_rate = r
                    break
            self.ads.data_rate = selected_rate
            logging.info(f"ADS1115 data rate configured to {selected_rate} SPS")

        def read(self):
            # return raw ADC voltage (or scaled value)
            return self.chan.voltage
except Exception:
    ADS1115ADC = None

class Datalogger:
    def __init__(self, data_dir="data", filename_prefix="log", sample_hz=100, adc=None, retention_days=5, adc_address=0x48, adc_channel=0, batch_size=400, batch_interval_ms=1000, analysis_config=None):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.filename_prefix = filename_prefix
        self.sample_hz = max(1, min(860, int(sample_hz))) # Cap at 860Hz
        self.interval = 1.0 / float(self.sample_hz)
        
        # Batch writing settings
        self.batch_size = batch_size
        self.batch_interval_ms = batch_interval_ms
        self._batch_buffer = []
        self._last_flush_time = time.time()

        # Analysis
        from .analysis import StreamAnalyzer
        self.analysis_config = analysis_config or {}
        self.stream_analyzer = StreamAnalyzer(self.analysis_config)
        self._current_analysis = {'rms': 0.0, 'freq': 60.0, 'sags_swells': []}

        # Try to initialize the requested ADC hardware
        self.adc = adc
        if self.adc is None:
            if ADS1115ADC:
                try:
                    self.adc = ADS1115ADC(
                        address=adc_address, 
                        channel=adc_channel,
                        target_rate=self.sample_hz
                    )
                except Exception as e:
                    logging.error("--- HARDWARE INITIALIZATION FAILURE ---")
                    logging.error("Failed to initialize ADS1115 ADC: %s", e)
                    self.adc = MockADC()
            else:
                self.adc = MockADC()

        self._stop = threading.Event()
        self._thread = None
        self._buffer = deque(maxlen=int(self.sample_hz * 60))  # keep last 60s in memory
        self._current_date = None
        self._file = None
        self.retention_days = int(retention_days)
        self._sample_callbacks = []
        
        self._open_log_file_for_today()

    def get_current_analysis(self):
        return self._current_analysis

    def update_analysis_config(self, config):
        self.analysis_config.update(config)
        if self.stream_analyzer:
            self.stream_analyzer.update_config(config)

    # ... (other methods unchanged: add_sample_callback, remove_sample_callback) ...

    def set_sample_rate(self, sample_hz):
        """Change the sample rate dynamically (1-860 Hz)."""
        sample_hz = max(1, min(860, int(sample_hz)))  # Clamp to 1-860
        if sample_hz != self.sample_hz:
            self.sample_hz = sample_hz
            self.interval = 1.0 / float(self.sample_hz)
            
            # Update ADC rate if supported
            if hasattr(self.adc, 'set_rate'):
                try:
                    self.adc.set_rate(self.sample_hz)
                except Exception:
                    logging.warning("Failed to update ADC data rate")

            # Update buffer size to maintain 60s of data
            self._buffer = deque(self._buffer, maxlen=int(self.sample_hz * 60))
            logging.info(f"Sample rate changed to {self.sample_hz} Hz")
            return True
        return False

    # ... (unchanged: _log_filename_for_date, _open_log_file_for_today, _cleanup_old_logs, start, stop) ...

    def _flush_batch(self):
        if not self._batch_buffer:
            return
        
        try:
            writer = csv.writer(self._file)
            # Format numbers to reduce file size slightly? or keep full precision?
            # Keeping full precision for now, but could optimize.
            # writerows is faster than looping writerow
            writer.writerows([("{:.6f}".format(t), "{:.6f}".format(v)) for t, v in self._batch_buffer])
            
            try:
                self._file.flush()
                # fsync is expensive, only do it on flush
                os.fsync(self._file.fileno())
            except Exception:
                pass
            
            self._batch_buffer.clear()
            self._last_flush_time = time.time()
        except Exception:
            logging.exception("Failed to write batch to disk")

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
                # logging.exception("ADC read failed, using NaN: %s", e) # Reduce spam?
                val = float('nan')

            # Streaming Analysis
            try:
                metrics = self.stream_analyzer.process_sample(ts, val)
                self._current_analysis.update(metrics)
            except Exception:
                pass # Don't crash logging if analysis fails

            # Add to batch buffer
            self._batch_buffer.append((ts, val))
            
            # Check flush conditions
            now = time.time()
            if (len(self._batch_buffer) >= self.batch_size) or \
               ((now - self._last_flush_time) * 1000 >= self.batch_interval_ms):
                self._flush_batch()

            # Add to memory buffer (for UI)
            self._buffer.append((ts, val))

            # Notify callbacks of new sample (UI updates)
            for callback in self._sample_callbacks:
                try:
                    callback(ts, val)
                except Exception:
                    logging.exception("Error in sample callback")

            # sleep until next scheduled sample
            next_sample += self.interval
            sleep_for = next_sample - time.perf_counter()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                # we're behind schedule — skip sleeping to catch up
                next_sample = time.perf_counter()
        
        # Flush remaining on stop
        self._flush_batch()

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

    def get_range_from_file(self, filepath: str, start_ts: float, end_ts: float, max_points: int = 1000):
        """Return downsampled data from a specific CSV file in the range [start_ts, end_ts]."""
        if not os.path.exists(filepath):
            return []
        try:
            start_ts = float(start_ts)
            end_ts = float(end_ts)
        except Exception:
            return []
            
        bucket_count = max(1, int(max_points))
        interval = (end_ts - start_ts) / bucket_count
        buckets = [{'sum': 0.0, 'count': 0, 'min': None, 'max': None, 'ts_sum': 0.0} for _ in range(bucket_count)]

        try:
            with open(filepath, 'rt') as f:
                reader = csv.reader(f)
                next(reader, None) # skip header
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
                    if idx < 0: idx = 0
                    elif idx >= bucket_count: idx = bucket_count - 1
                    b = buckets[idx]
                    b['sum'] += val
                    b['count'] += 1
                    b['ts_sum'] += ts
                    if b['min'] is None or val < b['min']: b['min'] = val
                    if b['max'] is None or val > b['max']: b['max'] = val
        except Exception:
            logging.exception(f"Error processing CSV file {filepath}")
            return []

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
        filepath = self._log_filename_for_date(time.localtime())
        if not os.path.exists(filepath):
            return
        lines = []
        try:
            with open(filepath, "r") as f:
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
