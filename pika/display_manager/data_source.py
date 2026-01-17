"""Data source components for display information.

This module provides classes and functions for retrieving data from various sources
including voltage readings, anomaly counts, and network information.
"""

import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)


class VoltageDataSource:
    """Data source for voltage readings from the datalogger."""
    
    def __init__(self, logger_obj):
        """Initialize voltage data source.
        
        Args:
            logger_obj: Datalogger instance for reading voltage data
        """
        self.logger = logger_obj
    
    def get_current_voltage(self, query_seconds: float = 2.0) -> Optional[float]:
        """Get the most recent voltage reading.
        
        Args:
            query_seconds: How many seconds of recent data to query
            
        Returns:
            Current voltage in volts, or None if unavailable
        """
        try:
            data = self.logger.get_recent(seconds=query_seconds)
            if data:
                return float(data[-1][1])
        except Exception:
            logger.exception("Error reading current voltage from datalogger")
        return None


class AnomalyDataSource:
    """Data source for anomaly count from highlights file."""
    
    def __init__(self, data_dir: str = "data"):
        """Initialize anomaly data source.
        
        Args:
            data_dir: Directory containing highlights.json file
        """
        self.data_dir = data_dir
        self.highlights_path = os.path.join(data_dir, 'highlights.json')
    
    def get_recent_anomaly_count(self, hours: float = 3.0) -> int:
        """Count anomalies within the past specified hours.
        
        Args:
            hours: Number of hours to look back for anomalies
            
        Returns:
            Number of anomalies detected in the time window
        """
        if not os.path.exists(self.highlights_path):
            return 0
            
        try:
            with open(self.highlights_path, 'r') as f:
                highlights_data = json.load(f)
            
            cutoff_time = time.time() - (hours * 3600.0)
            return sum(
                1 for highlight in highlights_data
                if (highlight.get('end_ts', 0) >= cutoff_time or 
                    highlight.get('peak_ts', 0) >= cutoff_time)
            )
        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning("Failed to read highlights.json for anomaly count: %s", e)
            return 0


class NetworkDataSource:
    """Data source for network information."""
    
    @staticmethod
    def get_local_ip() -> Optional[str]:
        """Get the local IP address.
        
        Returns:
            Local IP address, or None if unable to determine
        """
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None
