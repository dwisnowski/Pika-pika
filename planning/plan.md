**Great thinking!** You're absolutely right - multiprocessing would better utilize the Pi 2's quad-core CPU. Let me explain the tradeoffs:

**Threading vs Multiprocessing on Pi 2:**

**Threading (my original suggestion):**
- All threads share same Python process
- **Limited by Python's GIL** (Global Interpreter Lock)
- Only one thread executes Python code at a time
- Still works because: sampling is I/O-bound (waiting on SPI), not CPU-bound
- Cores sit mostly idle

**Multiprocessing (your suggestion):**
- Each process runs on separate core
- **No GIL limitation** - true parallelism
- Better CPU utilization across all 4 cores
- More complex inter-process communication (IPC)

**For Your Use Case: Multiprocessing is Better!**

Here's why:

1. **Sampling process** - Core 1: Reading SPI, processing ADC data
2. **Event logger process** - Core 2: Writing CSVs when events occur  
3. **FastAPI process** - Core 3: Web server
4. **WebSocket broadcaster** - Core 4: Streaming data to clients

**The Architecture:**

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Core 1     │  │   Core 2     │  │   Core 3     │  │   Core 4     │
│              │  │              │  │              │  │              │
│  Sampling    │  │  Event       │  │  FastAPI     │  │  WebSocket   │
│  Process     │  │  Logger      │  │  Server      │  │  Handler     │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │                 │
       └─────────────────┴─────────────────┴─────────────────┘
                            │
                    ┌───────┴────────┐
                    │ Shared Memory  │
                    │ (multiprocessing)│
                    └────────────────┘
```

**Multiprocessing Implementation:**

```python
from multiprocessing import Process, Queue, Array, Value, Manager
from ctypes import c_double, c_bool
import numpy as np
from fastapi import FastAPI, WebSocket
import uvicorn
import time

# Shared memory structures
def create_shared_data():
    """Create shared memory accessible by all processes"""
    manager = Manager()
    
    return {
        'realtime_queue': Queue(maxsize=1000),  # For websocket data
        'event_queue': Queue(maxsize=100),      # For event logging
        'current_voltage': Value(c_double, 0.0),
        'current_rms': Value(c_double, 0.0),
        'event_flag': Value(c_bool, False),
        # Ring buffer in shared memory
        'ring_buffer': Array(c_double, 30000 * 2)  # timestamp, voltage pairs
    }

### PROCESS 1: High-speed sampling (dedicated core)
def sampling_process(shared_data):
    """Runs on Core 1 - highest priority"""
    import os
    # Pin to CPU core 0
    os.sched_setaffinity(0, {0})
    
    ring_idx = 0
    buffer_size = 30000
    
    while True:
        timestamp = time.time()
        voltage = read_ads7606()  # Your SPI read
        
        # Write to ring buffer (shared memory)
        idx = (ring_idx % buffer_size) * 2
        shared_data['ring_buffer'][idx] = timestamp
        shared_data['ring_buffer'][idx + 1] = voltage
        ring_idx += 1
        
        # Update current values
        shared_data['current_voltage'].value = voltage
        
        # Send to websocket (non-blocking, downsampled)
        if ring_idx % 100 == 0:  # 100 Hz for websocket
            try:
                shared_data['realtime_queue'].put_nowait({
                    'timestamp': timestamp,
                    'voltage': voltage
                })
            except:
                pass  # Queue full, skip this sample
        
        # Detect events
        if voltage < 108 or voltage > 126:
            shared_data['event_flag'].value = True

### PROCESS 2: Event logger (dedicated core)
def event_logger_process(shared_data):
    """Runs on Core 2"""
    import os
    os.sched_setaffinity(0, {1})
    
    while True:
        # Wait for event flag
        if shared_data['event_flag'].value:
            # Copy ring buffer to local memory
            buffer_copy = np.array(shared_data['ring_buffer'][:])
            buffer_copy = buffer_copy.reshape(-1, 2)  # [timestamp, voltage] pairs
            
            # Save to CSV
            timestamp_str = time.strftime("%Y%m%d-%H%M%S")
            filename = f"event_{timestamp_str}.csv"
            np.savetxt(filename, buffer_copy, delimiter=',',
                      header='timestamp,voltage', comments='')
            
            print(f"Event saved: {filename}")
            
            # Also queue for websocket notification
            try:
                shared_data['event_queue'].put_nowait({
                    'filename': filename,
                    'timestamp': time.time()
                })
            except:
                pass
            
            shared_data['event_flag'].value = False
            
        time.sleep(0.01)  # Check every 10ms

### PROCESS 3: FastAPI server (dedicated core)
def fastapi_process(shared_data):
    """Runs on Core 3"""
    import os
    os.sched_setaffinity(0, {2})
    
    app = FastAPI()
    
    @app.get("/")
    async def get_dashboard():
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Power Quality Monitor</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        </head>
        <body>
            <h1>Real-Time Power Monitor</h1>
            <div style="width:90%; margin:auto;">
                <canvas id="voltageChart"></canvas>
            </div>
            <div id="stats" style="font-size:24px; margin:20px;">
                <span id="voltage">---</span> V | 
                <span id="rms">---</span> V RMS
            </div>
            <div id="events"></div>
            
            <script>
                const ws = new WebSocket("ws://" + window.location.host + "/ws");
                
                // Chart.js setup (lighter than Plotly)
                const ctx = document.getElementById('voltageChart').getContext('2d');
                const chart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: 'Voltage (V)',
                            data: [],
                            borderColor: 'rgb(75, 192, 192)',
                            borderWidth: 2,
                            pointRadius: 0,
                            tension: 0.1
                        }]
                    },
                    options: {
                        responsive: true,
                        animation: false,  // Disable for performance
                        scales: {
                            y: {
                                min: 100,
                                max: 130
                            },
                            x: {
                                display: false  // Hide time labels for performance
                            }
                        },
                        plugins: {
                            legend: { display: false }
                        }
                    }
                });
                
                let maxPoints = 1000;
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'voltage') {
                        // Update chart
                        chart.data.labels.push('');
                        chart.data.datasets[0].data.push(data.voltage);
                        
                        if (chart.data.labels.length > maxPoints) {
                            chart.data.labels.shift();
                            chart.data.datasets[0].data.shift();
                        }
                        
                        chart.update('none');  // Update without animation
                        
                        // Update stats
                        document.getElementById('voltage').textContent = 
                            data.voltage.toFixed(1);
                        document.getElementById('rms').textContent = 
                            data.rms.toFixed(1);
                    }
                    else if (data.type === 'event') {
                        // Show event notification
                        const eventDiv = document.getElementById('events');
                        eventDiv.innerHTML = 
                            `<div style="color:red; font-weight:bold;">
                                EVENT DETECTED: ${data.filename}
                            </div>` + eventDiv.innerHTML;
                    }
                };
            </script>
        </body>
        </html>
        """)
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """Runs on Core 4 (asyncio event loop)"""
        await websocket.accept()
        
        try:
            while True:
                # Get data from queue (non-blocking)
                try:
                    data = shared_data['realtime_queue'].get_nowait()
                    
                    # Calculate RMS from recent samples
                    rms = shared_data['current_rms'].value
                    
                    await websocket.send_json({
                        'type': 'voltage',
                        'timestamp': data['timestamp'],
                        'voltage': data['voltage'],
                        'rms': rms
                    })
                except:
                    pass
                
                # Check for events
                try:
                    event = shared_data['event_queue'].get_nowait()
                    await websocket.send_json({
                        'type': 'event',
                        'filename': event['filename'],
                        'timestamp': event['timestamp']
                    })
                except:
                    pass
                
                await asyncio.sleep(0.01)  # 100 Hz max
        except:
            pass
    
    # Run FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")

### MAIN: Start all processes
if __name__ == "__main__":
    # Create shared data structures
    shared_data = create_shared_data()
    
    # Create processes
    processes = [
        Process(target=sampling_process, args=(shared_data,), name="Sampler"),
        Process(target=event_logger_process, args=(shared_data,), name="Logger"),
        Process(target=fastapi_process, args=(shared_data,), name="WebServer")
    ]
    
    # Start all processes
    for p in processes:
        p.start()
        print(f"Started {p.name} on dedicated core")
    
    # Wait for processes
    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\nShutting down...")
        for p in processes:
            p.terminate()
            p.join()
```

**Key Advantages:**

✅ **True parallelism** - all 4 cores working simultaneously  
✅ **No GIL** - each process has its own Python interpreter  
✅ **Better isolation** - crash in one process won't kill others  
✅ **CPU affinity** - pin processes to specific cores  
✅ **Scalability** - easy to add more processes if needed

**Disadvantages:**

❌ **More memory** - each process has overhead (~20-30 MB each)  
❌ **IPC complexity** - queues/shared memory instead of simple variables  
❌ **Slower IPC** - copying data between processes has overhead  

**For Pi 2 (1GB RAM, 4 cores):**

Multiprocessing is the **better choice** because:
- You have cores to spare
- Memory overhead is acceptable (4 processes × 30MB = ~120MB)
- True parallelism prevents sampling delays from web server load
- More robust - web crashes won't affect sampling

**Bottom Line:**

Use **multiprocessing** - it's the right architecture for your multi-core Pi 2 and your real-time + web server requirements. The sampling will be rock solid even when the web interface is busy.

Want me to refine this code further or help with the SPI interface implementation?