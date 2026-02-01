#!/usr/bin/env python3
"""
Process Status Monitor

This script shows the status of all Pika-pika multiprocessing components.
Use this to check if all processes are running and healthy.
"""

import sys
import os
import time
import json
from typing import Dict, Any

# Add the parent directory to Python path to import pika modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pika.config import ConfigurationManager
from pika.shared_memory import SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer


def check_shared_memory_status() -> Dict[str, Any]:
    """Check the status of shared memory buffers."""
    status = {
        'sample_buffer': {'available': False, 'info': None},
        'analysis_buffer': {'available': False, 'info': None},
        'config_buffer': {'available': False, 'info': None}
    }
    
    try:
        # Load configuration to get shared memory names
        config_manager = ConfigurationManager()
        config = config_manager.load_configuration()
        mp_config = config.get("multiprocessing", {})
        shared_memory_names = mp_config.get('shared_memory_names', {})
        
        # Check sample buffer
        try:
            sample_buffer = SharedSampleBuffer(
                create=False, 
                name=shared_memory_names.get('sample_buffer', 'pika_samples')
            )
            info = sample_buffer.get_buffer_info()
            status['sample_buffer'] = {
                'available': True,
                'info': info,
                'recent_samples': len(sample_buffer.read_all())
            }
            sample_buffer.cleanup()
        except Exception as e:
            status['sample_buffer']['error'] = str(e)
        
        # Check analysis buffer
        try:
            analysis_buffer = SharedAnalysisBuffer(
                create=False,
                name=shared_memory_names.get('analysis_buffer', 'pika_analysis')
            )
            analysis = analysis_buffer.get_current_analysis()
            info = analysis_buffer.get_buffer_info()
            status['analysis_buffer'] = {
                'available': True,
                'info': info,
                'current_analysis': analysis,
                'data_fresh': analysis_buffer.is_data_fresh()
            }
            analysis_buffer.cleanup()
        except Exception as e:
            status['analysis_buffer']['error'] = str(e)
        
        # Check config buffer
        try:
            config_buffer = SharedConfigBuffer(
                create=False,
                name=shared_memory_names.get('config_buffer', 'pika_config')
            )
            config_data, version = config_buffer.get_config()
            info = config_buffer.get_buffer_info()
            status['config_buffer'] = {
                'available': True,
                'info': info,
                'config_version': version,
                'sample_hz': config_data.get('sample_hz', 'unknown')
            }
            config_buffer.cleanup()
        except Exception as e:
            status['config_buffer']['error'] = str(e)
            
    except Exception as e:
        status['config_error'] = str(e)
    
    return status


def check_process_status() -> Dict[str, Any]:
    """Check if Pika-pika processes are running."""
    import psutil
    
    processes = {
        'datalogger': {'running': False, 'pids': []},
        'event_logger': {'running': False, 'pids': []},
        'fastapi': {'running': False, 'pids': []},
        'uvicorn': {'running': False, 'pids': []}
    }
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                
                # Check for datalogger process
                if 'datalogger' in cmdline.lower() or 'pika.datalogger' in cmdline:
                    processes['datalogger']['running'] = True
                    processes['datalogger']['pids'].append(proc.info['pid'])
                
                # Check for event logger process
                if 'event_logger' in cmdline.lower() or 'pika.event_logger' in cmdline:
                    processes['event_logger']['running'] = True
                    processes['event_logger']['pids'].append(proc.info['pid'])
                
                # Check for FastAPI/uvicorn process
                if ('pika.app' in cmdline) or \
                   ('uvicorn' in cmdline and 'pika' in cmdline) or \
                   ('python' in cmdline and '-m pika.app' in cmdline):
                    processes['fastapi']['running'] = True
                    processes['fastapi']['pids'].append(proc.info['pid'])
                    processes['uvicorn']['running'] = True
                    processes['uvicorn']['pids'].append(proc.info['pid'])
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
    except Exception as e:
        processes['error'] = str(e)
    
    return processes


def format_status_output(shared_memory_status: Dict[str, Any], process_status: Dict[str, Any]) -> str:
    """Format the status information for display."""
    output = []
    output.append("=" * 60)
    output.append("🔧 PIKA-PIKA MULTIPROCESSING STATUS")
    output.append("=" * 60)
    output.append("")
    
    # Shared Memory Status
    output.append("📊 SHARED MEMORY STATUS:")
    output.append("")
    
    for buffer_name, status in shared_memory_status.items():
        if buffer_name == 'config_error':
            output.append(f"❌ Configuration Error: {status}")
            continue
            
        if status['available']:
            output.append(f"✅ {buffer_name.replace('_', ' ').title()}: Available")
            if 'info' in status and status['info']:
                info = status['info']
                output.append(f"   Size: {info.get('size', 'unknown')}")
                if 'recent_samples' in status:
                    output.append(f"   Recent samples: {status['recent_samples']}")
                if 'data_fresh' in status:
                    freshness = "Fresh" if status['data_fresh'] else "Stale"
                    output.append(f"   Data: {freshness}")
                if 'config_version' in status:
                    output.append(f"   Config version: {status['config_version']}")
                    output.append(f"   Sample rate: {status.get('sample_hz', 'unknown')} Hz")
        else:
            output.append(f"❌ {buffer_name.replace('_', ' ').title()}: Not available")
            if 'error' in status:
                output.append(f"   Error: {status['error']}")
    
    output.append("")
    
    # Process Status
    output.append("🔄 PROCESS STATUS:")
    output.append("")
    
    if 'error' in process_status:
        output.append(f"❌ Process check error: {process_status['error']}")
    else:
        for process_name, status in process_status.items():
            if process_name == 'error':
                continue
                
            if status['running']:
                pids_str = ', '.join(map(str, status['pids']))
                output.append(f"✅ {process_name.replace('_', ' ').title()}: Running (PID: {pids_str})")
            else:
                output.append(f"❌ {process_name.replace('_', ' ').title()}: Not running")
    
    output.append("")
    
    # Overall Status
    shared_memory_ok = all(
        status.get('available', False) 
        for key, status in shared_memory_status.items() 
        if key != 'config_error'
    )
    processes_ok = any(
        status['running'] 
        for process_name, status in process_status.items() 
        if process_name != 'error'
    )
    
    if shared_memory_ok and processes_ok:
        output.append("🎉 SYSTEM STATUS: Multiprocessing system is running!")
    elif shared_memory_ok:
        output.append("⚠️  SYSTEM STATUS: Shared memory ready, but processes not detected")
    elif processes_ok:
        output.append("⚠️  SYSTEM STATUS: Processes running, but shared memory issues")
    else:
        output.append("❌ SYSTEM STATUS: System not running")
    
    output.append("")
    output.append("=" * 60)
    
    return "\n".join(output)


def main():
    """Main function to check and display status."""
    try:
        print("Checking Pika-pika multiprocessing status...")
        print()
        
        # Check shared memory status
        shared_memory_status = check_shared_memory_status()
        
        # Check process status
        process_status = check_process_status()
        
        # Format and display results
        status_output = format_status_output(shared_memory_status, process_status)
        print(status_output)
        
        # Return appropriate exit code
        shared_memory_ok = all(
            status.get('available', False) 
            for key, status in shared_memory_status.items() 
            if key != 'config_error'
        )
        processes_ok = any(
            status['running'] 
            for process_name, status in process_status.items() 
            if process_name != 'error'
        )
        
        if shared_memory_ok and processes_ok:
            return 0  # Success
        else:
            return 1  # Issues detected
            
    except KeyboardInterrupt:
        print("\n⚠️  Status check interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Status check failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())