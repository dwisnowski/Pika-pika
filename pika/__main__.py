"""
Entry point for running the multiprocessing datalogger application.

This allows the application to be run with:
    python -m pika
    python -m pika --config custom_config.toml
"""

import sys
from .main import main

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Multiprocessing Datalogger Application")
    parser.add_argument(
        "--config",
        default="config.toml",
        help="Path to configuration file (default: config.toml)"
    )
    
    args = parser.parse_args()
    
    try:
        main(args.config)
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        sys.exit(0)
    except Exception as e:
        print(f"Application failed to start: {e}")
        sys.exit(1)