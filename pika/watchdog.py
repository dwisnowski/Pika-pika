"""Systemd watchdog helper that reports READY and WATCHDOG=1 to systemd.

If a Datalogger instance is provided, the helper checks that samples are recent enough
(before sending WATCHDOG=1). If samples are stale (older than `stale_threshold` seconds),
it stops sending WATCHDOG messages so systemd will restart the service.
"""
from __future__ import annotations

import os
import threading
import time
import logging
from typing import Optional, Dict, Any

from .config import ConfigurationManager

logger = logging.getLogger(__name__)

try:
    from sdnotify import SystemdNotifier
except Exception:  # pragma: no cover - sdnotify may not be installed in tests
    SystemdNotifier = None


def start_watchdog(datalogger=None, stale_threshold: Optional[float] = None, config: Optional[Dict[str, Any]] = None):
    """Start a background thread that notifies systemd about readiness and health.

    - `datalogger` (optional): object with `get_recent(seconds)` method returning samples.
    - `stale_threshold` (optional): seconds allowed since last sample before considering the datalogger stale.
                                   If None, will be loaded from config.
    - `config` (optional): configuration dictionary. If None, will be loaded from config.toml.

    Returns a `stop_event` that can be set() to stop the background thread.
    If SystemdNotifier is unavailable or WATCHDOG_USEC is not set, the function will still send READY=1 if possible
    but will not start the periodic watchdog thread.
    """
    # Load configuration if not provided
    if config is None:
        try:
            config_manager = ConfigurationManager()
            full_config = config_manager.load_configuration()
            systemd_config = full_config.get("systemd", {})
        except Exception as e:
            logger.warning(f"Failed to load configuration: {e}, using defaults")
            systemd_config = {"enable_watchdog": True, "stale_threshold": 3.0}
    else:
        systemd_config = config.get("systemd", {"enable_watchdog": True, "stale_threshold": 3.0})
    
    # Use stale_threshold from parameter, config, or default
    if stale_threshold is None:
        stale_threshold = systemd_config.get("stale_threshold", 3.0)
    
    # Check if watchdog is enabled in configuration
    if not systemd_config.get("enable_watchdog", True):
        logger.info("Systemd watchdog disabled in configuration")
        return None
    
    notifier = None
    if SystemdNotifier is None:
        logger.info("sdnotify not available; systemd watchdog will be disabled")
        return None

    notifier = SystemdNotifier()

    # Notify ready (best-effort)
    try:
        notifier.notify("READY=1")
    except Exception:
        logger.exception("Failed to notify systemd READY=1")

    # See if WATCHDOG_USEC is set; if not, skip starting the watchdog loop
    # Note: This is a systemd-specific environment variable and should remain as os.environ.get
    usec = os.environ.get("WATCHDOG_USEC")
    if not usec:
        logger.info("WATCHDOG_USEC not set; systemd watchdog loop will not start")
        return None

    try:
        us = int(usec)
        interval = max(0.5, (us / 1e6) / 2.0)
    except Exception:
        interval = 5.0

    stop_event = threading.Event()

    def _loop():
        logger.info("Systemd watchdog loop starting (interval=%.2fs)", interval)
        while not stop_event.is_set():
            try:
                healthy = True
                if datalogger is not None:
                    try:
                        recent = datalogger.get_recent(seconds=10.0)
                        if not recent:
                            healthy = False
                        else:
                            last_ts = recent[-1][0]
                            if (time.time() - last_ts) > stale_threshold:
                                healthy = False
                    except Exception:
                        logger.exception("Error checking datalogger freshness")
                        healthy = False

                if healthy:
                    try:
                        notifier.notify("WATCHDOG=1")
                        logger.debug("Sent WATCHDOG=1 to systemd")
                    except Exception:
                        logger.exception("Failed to send WATCHDOG=1")
                else:
                    logger.warning("Datalogger reports stale or missing samples; skipping WATCHDOG ping to let systemd restart if configured")
                # sleep for interval
                time.sleep(interval)
            except Exception:
                logger.exception("Exception inside watchdog loop; continuing")

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return stop_event


def stop_watchdog(stop_event):
    if stop_event is not None:
        stop_event.set()
