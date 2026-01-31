"""Automatic route registration utility.

This module provides a centralized function to automatically register
all route handlers from the handlers package with the FastAPI app.
"""

from . import (
    register_health_routes, register_index_routes, register_api_recent_routes,
    register_api_highlights_routes, register_api_range_routes, register_api_config_routes,
    register_websocket_live_routes, register_websocket_demo_routes,
    register_demo_pages_routes, register_history_pages_routes,
    register_devtools_routes, register_api_analysis_routes
)


def register_all_routes(app, shared_sample_buffer, shared_config_buffer, logger, config, manager, static_dir, display_fps, display_auto_ip, data_dir):
    """Automatically register all routes from handlers package.
    
    Args:
        app: FastAPI application instance
        shared_sample_buffer: SharedSampleBuffer instance for recent data
        shared_config_buffer: SharedConfigBuffer instance for configuration
        logger: Datalogger instance (for range queries and fallback)
        config: Configuration dictionary
        manager: WebSocket connection manager
        static_dir: Static files directory
        display_fps: Display FPS setting
        display_auto_ip: Display auto IP setting
        data_dir: Data directory path
    """
    # Register core API routes
    register_health_routes(app, logger)
    register_index_routes(app)
    register_api_recent_routes(app, shared_sample_buffer)
    register_api_highlights_routes(app, app.state, data_dir)
    register_api_range_routes(app, logger)  # Still uses logger for CSV file reading
    register_api_config_routes(app, shared_config_buffer, config, manager, display_fps, display_auto_ip)
    
    # Register WebSocket routes (live only - demo registered separately)
    register_websocket_live_routes(app, manager, logger, app.state, data_dir)
    
    # Register demo page routes
    register_demo_pages_routes(app)
    
    # Register history page routes
    register_history_pages_routes(app)
    
    # Register DevTools integration
    register_devtools_routes(app)
    
    # Register Analysis API
    register_api_analysis_routes(app, logger)
