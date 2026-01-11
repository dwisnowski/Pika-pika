#!/usr/bin/env python3
"""Check if a port is open on localhost."""
import socket
import sys

def is_port_open(host='localhost', port=8000, timeout=1):
    """Check if port is open on host."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    if is_port_open(port=port):
        print(f"Error: App is already running on port {port}")
        print("   Stop the existing instance first or use a different port")
        sys.exit(1)
    else:
        print(f"Port {port} is free, starting app...")
        sys.exit(0)