"""Route handlers package for the Pika-pika web application.

This package contains individual modules for each route handler, following
single responsibility principle for better organization and maintainability.
"""

# Import handler functions
from .pages.health import health, register_health_routes
from .pages.index import index, register_index_routes
from .apis.api_recent import api_recent, register_api_recent_routes
from .apis.api_highlights import api_highlights, register_api_highlights_routes
from .apis.api_range import api_range, register_api_range_routes
from .apis.api_config import get_config, update_sample_rate, register_api_config_routes
from .apis.api_analysis_history import register_api_analysis_routes
from .websockets.websocket_live import websocket_live, register_websocket_live_routes
from .websockets.websocket_demo import websocket_demo, register_websocket_demo_routes
from .pages.demo_pages import demo, register_demo_pages_routes
from .pages.history_pages import register_history_pages_routes, history
from .apis.api_devtools import register_devtools_routes

# Import registration functions
from .router import register_all_routes

__all__ = [
    # Handler functions (for backward compatibility)
    'health', 'index', 'api_recent', 'api_highlights', 'api_range',
    'get_config', 'update_sample_rate', 'websocket_live', 'websocket_demo',
    'demo', 'history',
    
    # Registration functions (for individual route registration)
    'register_health_routes', 'register_index_routes', 'register_api_recent_routes',
    'register_api_highlights_routes', 'register_api_range_routes', 'register_api_config_routes',
    'register_websocket_live_routes', 'register_websocket_demo_routes',
    'register_demo_pages_routes',
    'register_history_pages_routes',
    'register_devtools_routes',
    
    # Automatic registration function
    'register_all_routes'
]
