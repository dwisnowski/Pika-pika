# Threading Mode Implementation Guide

## Overview

I've successfully implemented threading mode as an alternative to multiprocessing in your Pika-pika datalogger. This allows the system to run on single-processor systems while maintaining the same architecture and functionality.

## Key Changes Made

### 1. Configuration Updates

**config.toml** now supports execution mode selection:

```toml
[execution]
# Choose between "multiprocessing" or "threading"
mode = "threading"

[threading]
# Threading-specific settings (lighter than multiprocessing)
heartbeat_interval = 2.0
restart_delay = 1.0
max_restarts = 3
shutdown_timeout = 15.0

[multiprocessing]
# Original multiprocessing settings (kept for compatibility)
shared_memory_names = { sample_buffer = "pika_samples", analysis_buffer = "pika_analysis", config_buffer = "pika_config" }
heartbeat_interval = 5.0
restart_delay = 2.0
max_restarts = 5
shutdown_timeout = 30.0
```

### 2. New Threading Components

#### ThreadSupervisor (`pika/thread_supervisor.py`)
- Manages threads instead of processes
- Provides health monitoring and restart capabilities
- Uses cooperative shutdown (threads check `shutdown_event`)
- Lower overhead than ProcessSupervisor

#### Threading Workers (`pika/threading_workers.py`)
- **SharedData**: Thread-safe data structure replacing shared memory
- **ThreadingDatalogger**: Thread-based datalogger using queues
- **ThreadingEventLogger**: Thread-based analysis engine
- **ThreadingWebServer**: Thread-based web server

### 3. Updated Main Application

**pika/main.py** now automatically detects execution mode and:
- Uses appropriate supervisor (ProcessSupervisor vs ThreadSupervisor)
- Initializes correct shared resources (shared memory vs shared data)
- Manages components based on execution mode

## Usage

### Running in Threading Mode

1. **Set execution mode in config.toml:**
   ```toml
   [execution]
   mode = "threading"
   ```

2. **Run the application:**
   ```bash
   uv run python -m pika.main
   ```

3. **The application will automatically:**
   - Detect threading mode from config
   - Initialize shared data structures (queues, locks)
   - Start all components as threads
   - Monitor thread health and restart failed threads

### Running in Multiprocessing Mode (Default)

1. **Set execution mode in config.toml:**
   ```toml
   [execution]
   mode = "multiprocessing"
   ```

2. **Run the application:**
   ```bash
   uv run python -m pika.main
   ```

## Architecture Comparison

### Multiprocessing Mode
- **Pros**: True parallelism, process isolation, CPU affinity
- **Cons**: Higher memory usage, shared memory complexity
- **Best for**: Multi-core systems, production deployments

### Threading Mode  
- **Pros**: Lower memory usage, simpler data sharing, single process
- **Cons**: GIL limitations, shared state complexity
- **Best for**: Single-core systems, development, testing

## Data Flow

### Multiprocessing Mode
```
DataloggerProcess → SharedSampleBuffer → EventLoggerProcess → SharedAnalysisBuffer → FastAPIProcess
```

### Threading Mode
```
ThreadingDatalogger → sample_queue → ThreadingEventLogger → analysis_data (dict) → ThreadingWebServer
```

## Configuration Validation

The ConfigurationManager now validates both execution modes:

- **execution.mode**: Must be "multiprocessing" or "threading"
- **threading.heartbeat_interval**: 0.5-30.0 seconds
- **threading.restart_delay**: 0.1-10.0 seconds  
- **threading.max_restarts**: 0-10 attempts
- **threading.shutdown_timeout**: 5.0-120.0 seconds

## Benefits of Threading Mode

1. **Single Process**: Easier debugging and monitoring
2. **Lower Memory**: No shared memory overhead
3. **Simpler Deployment**: One process to manage
4. **Development Friendly**: Easier to debug with standard tools
5. **Resource Efficient**: Better for constrained environments

## Monitoring and Status

Both modes provide the same status interface:

```python
app = MultiprocessingApplication("config.toml")
status = app.get_status()

# Status includes:
# - execution_mode: "threading" or "multiprocessing"  
# - components: Status of all threads/processes
# - shared resources: Queue sizes or buffer info
# - supervisor_running: Health monitoring status
```

## Error Handling

Threading mode includes comprehensive error handling:

- **Thread Failures**: Automatic restart within limits
- **Graceful Shutdown**: Cooperative shutdown using events
- **Resource Cleanup**: Automatic cleanup of shared resources
- **Error Logging**: Same error handling system as multiprocessing

## Testing

The implementation includes validation that:
- Configuration loads correctly for both modes
- SharedData structures work properly
- ThreadSupervisor manages threads correctly
- Components communicate through queues and shared data

## Migration Guide

To switch from multiprocessing to threading:

1. **Update config.toml:**
   ```toml
   [execution]
   mode = "threading"
   ```

2. **Adjust threading settings if needed:**
   ```toml
   [threading]
   heartbeat_interval = 2.0  # Faster than multiprocessing
   max_restarts = 3          # Fewer restarts needed
   shutdown_timeout = 15.0   # Faster shutdown
   ```

3. **No code changes required** - the application automatically adapts

## Performance Considerations

### Threading Mode is Better For:
- Single-core systems
- Development environments
- Memory-constrained systems
- Simple deployments

### Multiprocessing Mode is Better For:
- Multi-core systems
- CPU-intensive workloads
- Production environments
- Maximum isolation requirements

The implementation maintains full compatibility - you can switch between modes by simply changing the configuration file.