# WebSocket Connection Management Package

This package provides connection managers for different WebSocket endpoints in the Pika-pika web application, following single responsibility principle for better organization and maintainability.

## Package Structure

```
websocket/
├── __init__.py          # Package exports
├── live_manager.py       # Live data WebSocket manager
├── demo_manager.py       # Demo data WebSocket manager
└── README.md            # This file
```

## Connection Managers

### LiveConnectionManager (`live_manager.py`)

Handles real-time data streaming for live voltage measurements from the datalogger.

**Features:**
- Thread-safe sample queuing
- Automatic broadcast task management
- Dead connection cleanup
- Real-time data streaming

**Usage:**
```python
from .websocket import ConnectionManager

manager = ConnectionManager()
await manager.connect(websocket)
manager.add_sample(timestamp, voltage)
```

### DemoConnectionManager (`demo_manager.py`)

Handles real-time demo data streaming for testing without hardware.

**Features:**
- Simulated voltage data with realistic anomalies
- Automatic anomaly generation (spikes and drops)
- Real-time highlights calculation
- Demo data streaming

**Usage:**
```python
from .websocket import DemoConnectionManager

demo_manager = DemoConnectionManager()
await demo_manager.connect(websocket)
# Automatic simulation starts on first connection
```

## Key Design Patterns

### 1. Connection Lifecycle Management
```python
async def connect(self, websocket: WebSocket):
    await websocket.accept()
    self.active_connections.append(websocket)

def disconnect(self, websocket: WebSocket):
    self.active_connections.remove(websocket)
```

### 2. Broadcasting with Error Handling
```python
async def broadcast(self, message: str):
    for connection in self.active_connections:
        try:
            await connection.send_text(message)
        except Exception:
            self.active_connections.remove(connection)
```

### 3. Thread-Safe Operations
```python
def add_sample(self, ts: float, val: float):
    asyncio.run_coroutine_threadsafe(
        self.sample_queue.put((ts, val)),
        asyncio.get_event_loop()
    )
```

## Benefits of This Structure

1. **Single Responsibility**: Each manager handles one specific WebSocket type
2. **Reusability**: Managers can be used in different contexts
3. **Testability**: Each manager can be tested independently
4. **Maintainability**: WebSocket logic separated from route handlers
5. **Scalability**: Easy to add new WebSocket types
6. **Error Resilience**: Robust connection and error handling

## Integration with Route Handlers

The managers are used by WebSocket route handlers:

```python
# In websocket_live.py
async def websocket_live(websocket: WebSocket, manager, ...):
    await manager.connect(websocket)
    try:
        # WebSocket communication
    finally:
        manager.disconnect(websocket)

# In app.py
from .websocket import ConnectionManager, DemoConnectionManager

manager = ConnectionManager()
demo_manager = DemoConnectionManager()
```

## Migration Notes

- **Extracted from app.py**: WebSocket managers moved to dedicated package
- **Cleaner separation**: WebSocket logic separated from HTTP route logic
- **Better organization**: Related WebSocket functionality grouped together
- **Enhanced maintainability**: Easier to modify WebSocket behavior
- **Same functionality**: All WebSocket features preserved

This separation makes the WebSocket codebase much more maintainable and easier to understand!
