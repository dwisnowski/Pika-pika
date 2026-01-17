# Route Handlers Package

This package contains individual modules for each route handler in the Pika-pika web application, following single responsibility principle for better organization and maintainability.

## Package Structure

```
handlers/
├── __init__.py          # Package exports and automatic registration
├── router.py            # Centralized automatic route registration
├── health.py            # Health check endpoint
├── index.py             # Main index page
├── api_recent.py        # Recent data API endpoint
├── api_highlights.py    # Highlights API endpoint
├── api_range.py         # Range data API endpoint
├── api_config.py        # Configuration API endpoints
├── websocket_live.py    # Live WebSocket endpoint
├── websocket_demo.py    # Demo WebSocket endpoint
├── demo_pages.py        # Demo page endpoints
├── api_demo.py          # Demo API endpoints
└── README.md           # This file
```

## Automatic Route Registration

The package now supports **automatic route registration** - no manual route definitions needed in `app.py`!

### Usage in Main App

```python
from .handlers import register_all_routes, register_websocket_demo_routes

# Automatically register all routes (except demo WebSocket)
register_all_routes(app, logger, config, manager, static_dir, DISPLAY_FPS, DISPLAY_AUTO_IP, DATA_DIR)

# Register demo WebSocket separately (has demo_manager dependency)
register_websocket_demo_routes(app, demo_manager)
```

## Handler Modules

### Core API Endpoints

- **`health.py`**: Health check for monitoring and systemd
- **`index.py`**: Main application index page
- **`api_recent.py`**: Recent voltage measurements
- **`api_highlights.py`**: Anomaly highlights with filtering
- **`api_range.py`**: Downsampled data for time ranges
- **`api_config.py`**: Configuration management

### WebSocket Endpoints

- **`websocket_live.py`**: Real-time live data streaming
- **`websocket_demo.py`**: Demo data streaming for testing

### Demo Endpoints

- **`demo_pages.py`**: Demo and history pages
- **`api_demo.py`**: Mocked data endpoints for testing

## Handler Function Patterns

Each handler module now contains:

1. **Handler Function**: The actual route logic
2. **Registration Function**: Automatically registers the route with FastAPI

### Example Handler (`health.py`)

```python
def health(logger):
    """Handler function with business logic."""
    # ... implementation

def register_health_routes(app: FastAPI, logger):
    """Registration function that adds routes to FastAPI app."""
    app.get('/health')(lambda: health(logger))
```

## Benefits of This Structure

1. **Single Responsibility**: Each file handles one specific endpoint or related group
2. **Automatic Registration**: No manual route definitions needed in main app
3. **Maintainability**: Easy to locate and modify specific functionality
4. **Testability**: Each handler can be tested in isolation
5. **Readability**: Smaller, focused files are easier to understand
6. **Extensibility**: Easy to add new endpoints - just create handler and add to router
7. **Organization**: Clear separation between different types of endpoints

## Adding New Handlers

To add a new endpoint:

1. **Create handler file** (e.g., `new_endpoint.py`):
```python
from fastapi import FastAPI

def handler_function(param1, param2):
    # Your logic here
    return result

def register_new_endpoint_routes(app: FastAPI, dependencies):
    app.get("/new-endpoint")(lambda p1, p2: handler_function(p1, p2))
```

2. **Update `__init__.py`**:
```python
from .new_endpoint import handler_function, register_new_endpoint_routes
```

3. **Update `router.py`**:
```python
def register_all_routes(app, ...):
    # ... existing registrations
    register_new_endpoint_routes(app, dependencies)
```

4. **Update exports in `__init__.py`**:
```python
__all__ = [
    # ... existing exports
    'handler_function', 'register_new_endpoint_routes'
]
```

## Migration Notes

- **All route decorators moved** from `app.py` to individual handler files
- **Automatic registration** eliminates need for manual route definitions
- **Same functionality preserved** - all endpoints work identically
- **Cleaner `app.py`** - now focuses on app configuration and lifecycle

The main `app.py` file now focuses on:
- Application configuration
- Middleware setup
- Lifecycle events
- Automatic route registration
- WebSocket connection management

This separation makes the codebase much more maintainable and easier to understand!
