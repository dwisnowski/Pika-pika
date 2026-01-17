"""WebSocket connection management package.

This package provides connection managers for different WebSocket endpoints,
including live data streaming and demo data simulation.
"""

from .live_manager import ConnectionManager
from .demo_manager import DemoConnectionManager

__all__ = ['ConnectionManager', 'DemoConnectionManager']
