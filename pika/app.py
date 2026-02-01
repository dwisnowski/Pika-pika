"""FastAPI webserver that uses shared memory for multiprocessing architecture."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import time
import json
import asyncio
from typing import List, Optional
from asyncio import Queue
try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback for older versions

from fastapi.templating import Jinja2Templates
from .shared_memory import SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer
from .process_supervisor import ProcessSupervisor
from . import demo
from .handlers import register_all_routes, register_websocket_demo_routes
from .websocket import ConnectionManager, DemoConnectionManager

app = FastAPI(title="Pika-pika")

# Initialize Jinja2 templates
templates = Jinja2Templates(directory="pika/templates")

# Lightweight CORS (adjust origins in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS", "HEAD", "PUT", "DELETE"],
    allow_headers=["*"],
    allow_credentials=True,
)

def load_config():
    """Load configuration from config.toml file."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.toml")
    if not os.path.exists(config_path):
        # Create default config if it doesn't exist
        return {
            "pika": {
                "sample_hz": 100,
                "data_dir": "data",
                "port": 8000,
                "display_fps": 5.0,
                "display_auto_ip": True
            },
            "pins": {
                "adc_address": 0x48,
                "adc_channel": 0,
                "lcd_port": 0,
                "lcd_device": 0,
                "lcd_cs": 8,
                "lcd_dc": 25,
                "lcd_rst": 27,
                "lcd_bl": 24
            }
        }

    with open(config_path, "rb") as f:
        return tomllib.load(f)

# Load configuration
full_config = load_config()
config = full_config.get("pika", {})
pins = full_config.get("pins", {})
dl_config = full_config.get("datalogger", {})
analysis_config = full_config.get("analysis", {})

DATA_DIR = config.get("data_dir", "data")
SAMPLE_HZ = config.get("sample_hz", 100)
DISPLAY_FPS = config.get("display_fps", 5.0)
DISPLAY_AUTO_IP = config.get("display_auto_ip", True)

# Initialize shared memory buffers (attach to existing ones created by process supervisor)
shared_sample_buffer: Optional[SharedSampleBuffer] = None
shared_analysis_buffer: Optional[SharedAnalysisBuffer] = None
shared_config_buffer: Optional[SharedConfigBuffer] = None
process_supervisor: Optional[ProcessSupervisor] = None

# Initialize connection managers (will be updated with shared memory buffers after initialization)
manager = ConnectionManager()
demo_manager = DemoConnectionManager(data_dir=DATA_DIR)

# Create a minimal datalogger instance for CSV file reading (range queries)
# This is only used for historical data access, not for sampling
class MinimalDatalogger:
    """Minimal datalogger for CSV file reading only."""
    def __init__(self, data_dir: str, filename_prefix: str = "log"):
        self.data_dir = data_dir
        self.filename_prefix = filename_prefix
    
    def _log_filename_for_date(self, date_struct):
        """Generate log filename for a given date."""
        date_str = time.strftime("%Y-%m-%d", date_struct)
        return os.path.join(self.data_dir, f"{self.filename_prefix}_{date_str}.csv")
    
    def get_range(self, start_ts: float, end_ts: float, max_points: int = 1000):
        """Return downsampled data in the range [start_ts, end_ts].

        Performs streaming bucketing to produce at most `max_points` samples by averaging
        values that fall into the same time bucket. Returns a list of (ts, value) tuples.
        """
        import csv
        import logging
        
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
        import csv
        import logging
        
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

minimal_logger = MinimalDatalogger(DATA_DIR)

def initialize_process_supervisor():
    """Initialize process supervisor for standalone operation (development mode)."""
    global process_supervisor
    
    # Only initialize process supervisor if running in standalone mode
    # (when not launched by the main multiprocessing application)
    if os.environ.get('PIKA_MULTIPROCESSING_MODE') != 'true':
        try:
            from .main import MultiprocessingApplication
            
            # Check if we should run in multiprocessing mode
            if os.environ.get('PIKA_ENABLE_MULTIPROCESSING', 'false').lower() == 'true':
                import logging as _logging
                _logging.getLogger(__name__).info("Multiprocessing mode enabled, but running FastAPI standalone")
                _logging.getLogger(__name__).info("Consider using 'python -m pika.main' for full multiprocessing")
            
        except ImportError:
            pass  # Main module not available
    
    # For now, we don't initialize a process supervisor in the FastAPI process
    # The process supervisor is handled by the main application
    process_supervisor = None

# static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

def initialize_shared_memory():
    """Initialize or attach to shared memory buffers created by process supervisor."""
    global shared_sample_buffer, shared_analysis_buffer, shared_config_buffer, manager
    
    try:
        # Get shared memory names from environment variables (set by process supervisor)
        sample_buffer_name = os.environ.get('PIKA_SAMPLE_BUFFER_NAME', 'pika_samples')
        analysis_buffer_name = os.environ.get('PIKA_ANALYSIS_BUFFER_NAME', 'pika_analysis')
        config_buffer_name = os.environ.get('PIKA_CONFIG_BUFFER_NAME', 'pika_config')
        
        # Attach to existing shared memory created by process supervisor
        shared_sample_buffer = SharedSampleBuffer(
            create=False, 
            name=sample_buffer_name
        )
        shared_analysis_buffer = SharedAnalysisBuffer(
            create=False,
            name=analysis_buffer_name
        )
        shared_config_buffer = SharedConfigBuffer(
            create=False,
            name=config_buffer_name
        )
        
        # Update connection manager with shared memory buffers
        manager.sample_buffer = shared_sample_buffer
        manager.analysis_buffer = shared_analysis_buffer
        
        import logging as _logging
        _logging.getLogger(__name__).info("Successfully attached to shared memory buffers")
        
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).exception("Failed to attach to shared memory")
        
        # Fallback: create new shared memory buffers for standalone operation
        # This allows the FastAPI process to run independently for development/testing
        try:
            shared_sample_buffer = SharedSampleBuffer(create=True)
            shared_analysis_buffer = SharedAnalysisBuffer(create=True)
            shared_config_buffer = SharedConfigBuffer(create=True)
            
            # Initialize config buffer with current configuration
            config_data = {
                'sample_hz': SAMPLE_HZ,
                'batch_size': dl_config.get('batch_size', 100),
                'batch_interval_ms': dl_config.get('batch_interval_ms', 1000),
                'analysis_config': analysis_config,
                'display_fps': DISPLAY_FPS
            }
            shared_config_buffer.update_config(config_data)
            
            # Update connection manager with shared memory buffers
            manager.sample_buffer = shared_sample_buffer
            manager.analysis_buffer = shared_analysis_buffer
            
            _logging.getLogger(__name__).warning("Created new shared memory buffers (standalone mode)")
            
        except Exception as fallback_error:
            _logging.getLogger(__name__).error(f"Failed to create fallback shared memory: {fallback_error}")
            # Continue without shared memory (graceful degradation)
            shared_sample_buffer = None
            shared_analysis_buffer = None
            shared_config_buffer = None

# Automatically register all routes from handlers package
# Note: We pass shared memory buffers instead of the datalogger
register_all_routes(
    app, 
    shared_sample_buffer, 
    shared_config_buffer, 
    minimal_logger,  # Only for CSV file reading
    config, 
    manager, 
    static_dir, 
    DISPLAY_FPS, 
    DISPLAY_AUTO_IP, 
    DATA_DIR
)

# Register demo WebSocket route (has dependency on demo_manager)
register_websocket_demo_routes(app, demo_manager)

@app.on_event("startup")
def startup_event():
    # Initialize process supervisor (for standalone mode)
    initialize_process_supervisor()
    
    # Initialize shared memory buffers
    initialize_shared_memory()
    
    # Clear demo files to ensure each run starts fresh
    demo_csv = os.path.join(DATA_DIR, "demo.csv")
    demo_highlights = os.path.join(DATA_DIR, "demo_highlights.json")
    for f in [demo_csv, demo_highlights]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                import logging as _logging
                _logging.getLogger(__name__).exception(f"Failed to remove {f}")

    # Start the WebSocket broadcast task
    asyncio.create_task(manager.start_broadcast_task())

    # Note: In multiprocessing mode, datalogger initialization, sample callbacks, 
    # display manager, watchdog, and highlights manager are handled by separate processes.
    # The FastAPI process only handles web serving and API endpoints.

@app.on_event("shutdown")
def shutdown_event():
    # Clean up process supervisor if running in standalone mode
    if process_supervisor:
        try:
            process_supervisor.graceful_shutdown()
        except Exception:
            import logging as _logging
            _logging.getLogger(__name__).exception("Error shutting down process supervisor")
    
    # Clean up shared memory resources
    # Note: In multiprocessing mode, shared memory cleanup is handled by the main application
    # In standalone mode, we clean up our own shared memory
    if os.environ.get('PIKA_MULTIPROCESSING_MODE') != 'true':
        if shared_sample_buffer:
            try:
                shared_sample_buffer.cleanup()
            except Exception:
                pass
        if shared_analysis_buffer:
            try:
                shared_analysis_buffer.cleanup()
            except Exception:
                pass
        if shared_config_buffer:
            try:
                shared_config_buffer.cleanup()
            except Exception:
                pass


if __name__ == "__main__":
    import uvicorn
    
    # Check if multiprocessing mode is requested
    enable_multiprocessing = os.environ.get('PIKA_ENABLE_MULTIPROCESSING', 'false').lower() == 'true'
    
    if enable_multiprocessing:
        # Use the main multiprocessing application
        try:
            from .main import main
            print("Starting in multiprocessing mode...")
            main()
        except ImportError:
            print("Multiprocessing mode not available, falling back to standalone FastAPI")
            uvicorn.run("pika.app:app", host="0.0.0.0", port=8000, log_level="info")
    else:
        # Run standalone FastAPI server (development mode)
        print("Starting in standalone FastAPI mode...")
        print("Set PIKA_ENABLE_MULTIPROCESSING=true to enable multiprocessing mode")
        uvicorn.run("pika.app:app", host="0.0.0.0", port=8000, log_level="info")
