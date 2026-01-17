#!/usr/bin/env python3
"""
Script to check if pika-pika application is running.
Used by Makefile stop-restart target.
"""

import psutil
import sys
import time


def is_pika_running():
    """Check if any pika-pika processes are running."""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # Use as_dict() to get process info as dictionary for psutil 7.2.1+
            proc_info = proc.info
            
            # Check if 'name' key exists in proc_info
            name = proc_info.get('name', '')
            if name and 'pika' in name.lower() and 'uvicorn' in name.lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def main():
    """Main function."""
    if is_pika_running():
        print("pika-pika application is already running")
        sys.exit(1)
    else:
        print("No pika-pika application found running")
        sys.exit(0)


if __name__ == "__main__":
    main()
