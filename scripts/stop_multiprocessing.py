#!/usr/bin/env python3
"""
Stop Multiprocessing System

This script forcefully stops all Pika-pika multiprocessing components.
Use this when Ctrl+C doesn't work or processes are stuck.
"""

import sys
import os
import time
import signal
import psutil
from typing import List, Dict, Any

# Add the parent directory to Python path to import pika modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pika.config import ConfigurationManager
from pika.shared_memory import SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer


def find_pika_processes() -> List[Dict[str, Any]]:
    """Find all Pika-pika related processes."""
    processes = []
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                name = proc.info['name'] or ''
                
                # Check for various Pika-pika processes
                is_pika_process = any([
                    'pika' in cmdline.lower(),
                    'pika.main' in cmdline,
                    'pika.app' in cmdline,
                    'pika.datalogger' in cmdline,
                    'pika.event_logger' in cmdline,
                    ('uvicorn' in cmdline and 'pika' in cmdline),
                    ('python' in cmdline and 'pika' in cmdline)
                ])
                
                if is_pika_process:
                    processes.append({
                        'pid': proc.info['pid'],
                        'name': name,
                        'cmdline': cmdline,
                        'process': proc
                    })
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
    except Exception as e:
        print(f"Error finding processes: {e}")
    
    return processes


def cleanup_shared_memory() -> None:
    """Clean up shared memory resources."""
    print("🧹 Cleaning up shared memory...")
    
    try:
        # Load configuration to get shared memory names
        config_manager = ConfigurationManager()
        config = config_manager.load_configuration()
        mp_config = config.get("multiprocessing", {})
        shared_memory_names = mp_config.get('shared_memory_names', {})
        
        # Clean up each buffer
        for buffer_type, default_name in [
            ('sample_buffer', 'pika_samples'),
            ('analysis_buffer', 'pika_analysis'),
            ('config_buffer', 'pika_config')
        ]:
            buffer_name = shared_memory_names.get(buffer_type, default_name)
            try:
                if buffer_type == 'sample_buffer':
                    buffer = SharedSampleBuffer(create=False, name=buffer_name)
                elif buffer_type == 'analysis_buffer':
                    buffer = SharedAnalysisBuffer(create=False, name=buffer_name)
                else:  # config_buffer
                    buffer = SharedConfigBuffer(create=False, name=buffer_name)
                
                buffer.cleanup()
                print(f"   ✅ Cleaned up {buffer_type}")
                
            except Exception as e:
                print(f"   ⚠️  {buffer_type}: {e}")
                
    except Exception as e:
        print(f"   ❌ Error during shared memory cleanup: {e}")


def stop_processes(processes: List[Dict[str, Any]], force: bool = False) -> bool:
    """Stop the found processes."""
    if not processes:
        print("✅ No Pika-pika processes found running")
        return True
    
    print(f"🛑 Found {len(processes)} Pika-pika process(es) to stop:")
    for proc_info in processes:
        print(f"   PID {proc_info['pid']}: {proc_info['name']}")
    
    success = True
    
    # First try graceful shutdown
    if not force:
        print("\n📤 Attempting graceful shutdown...")
        for proc_info in processes:
            try:
                proc = proc_info['process']
                if proc.is_running():
                    print(f"   Sending SIGTERM to PID {proc_info['pid']}")
                    proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                print(f"   ⚠️  PID {proc_info['pid']}: {e}")
        
        # Wait for graceful shutdown
        print("   Waiting 5 seconds for graceful shutdown...")
        time.sleep(5)
        
        # Check if processes are still running
        still_running = []
        for proc_info in processes:
            try:
                if proc_info['process'].is_running():
                    still_running.append(proc_info)
            except psutil.NoSuchProcess:
                pass  # Process already gone
        
        processes = still_running
    
    # Force kill remaining processes
    if processes:
        print(f"\n💥 Force killing {len(processes)} remaining process(es)...")
        for proc_info in processes:
            try:
                proc = proc_info['process']
                if proc.is_running():
                    print(f"   Force killing PID {proc_info['pid']}")
                    proc.kill()
                    proc.wait(timeout=3)
            except (psutil.NoSuchProcess, psutil.TimeoutExpired, psutil.AccessDenied) as e:
                print(f"   ⚠️  PID {proc_info['pid']}: {e}")
                success = False
    
    return success


def main():
    """Main function."""
    print("🔧 Pika-pika Multiprocessing Stop Script")
    print("=" * 50)
    
    force = '--force' in sys.argv or '-f' in sys.argv
    
    try:
        # Find all Pika-pika processes
        print("🔍 Searching for Pika-pika processes...")
        processes = find_pika_processes()
        
        # Stop processes
        success = stop_processes(processes, force=force)
        
        # Clean up shared memory
        cleanup_shared_memory()
        
        print("\n" + "=" * 50)
        if success:
            print("✅ Multiprocessing system stopped successfully!")
            return 0
        else:
            print("⚠️  Some processes may still be running. Try with --force flag.")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️  Stop script interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Stop script failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())