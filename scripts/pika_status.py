#!/usr/bin/env python3
"""
Pika-pika Status Monitor

Unified script that combines process checking and detailed status monitoring.
Supports both 'python -m pika.main' and 'uvicorn pika.app:app' execution methods.

Usage:
    python scripts/pika_status.py              # Detailed status report
    python scripts/pika_status.py --check      # Simple running check (exit codes)
    python scripts/pika_status.py --json       # JSON output for automation
"""

import sys
import os
import time
import json
import argparse
from typing import Dict, Any, Tuple

# Add the parent directory to Python path to import pika modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pika.config import ConfigurationManager
from pika.shared_memory import SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer


def check_pika_processes() -> Dict[str, Any]:
    """Check if Pika-pika processes are running."""
    import psutil
    
    processes = {
        'datalogger': {'running': False, 'pids': [], 'cmdlines': []},
        'event_logger': {'running': False, 'pids': [], 'cmdlines': []},
        'fastapi': {'running': False, 'pids': [], 'cmdlines': []},
        'main_process': {'running': False, 'pids': [], 'cmdlines': []}
    }
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                
                # Check for datalogger process
                if ('datalogger' in cmdline.lower() or 
                    'pika.datalogger' in cmdline or
                    'datalogger_process' in cmdline):
                    processes['datalogger']['running'] = True
                    processes['datalogger']['pids'].append(proc.info['pid'])
                    processes['datalogger']['cmdlines'].append(cmdline)
                
                # Check for event logger process
                if ('event_logger' in cmdline.lower() or 
                    'pika.event_logger' in cmdline or
                    'event_logger_process' in cmdline):
                    processes['event_logger']['running'] = True
                    processes['event_logger']['pids'].append(proc.info['pid'])
                    processes['event_logger']['cmdlines'].append(cmdline)
                
                # Check for FastAPI/uvicorn process (uvicorn pika.app:app)
                if (('uvicorn' in cmdline and 'pika.app' in cmdline) or
                    ('uvicorn' in cmdline and 'pika' in cmdline)):
                    processes['fastapi']['running'] = True
                    processes['fastapi']['pids'].append(proc.info['pid'])
                    processes['fastapi']['cmdlines'].append(cmdline)
                
                # Check for main process (python -m pika.main)
                if (('python' in cmdline and '-m pika.main' in cmdline) or
                    ('pika.main' in cmdline and 'python' in cmdline)):
                    processes['main_process']['running'] = True
                    processes['main_process']['pids'].append(proc.info['pid'])
                    processes['main_process']['cmdlines'].append(cmdline)
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
    except Exception as e:
        processes['error'] = str(e)
    
    return processes


def is_any_pika_running(processes: Dict[str, Any]) -> bool:
    """Check if any pika-pika processes are running."""
    if 'error' in processes:
        return False
    
    return any(
        status['running'] 
        for process_name, status in processes.items() 
        if process_name != 'error' and isinstance(status, dict)
    )


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


def get_execution_mode(processes: Dict[str, Any]) -> str:
    """Determine the execution mode based on running processes."""
    if processes.get('main_process', {}).get('running'):
        return "multiprocessing"  # python -m pika.main
    elif processes.get('fastapi', {}).get('running'):
        return "single_process"   # uvicorn pika.app:app
    else:
        return "none"


def format_detailed_status(processes: Dict[str, Any], shared_memory_status: Dict[str, Any]) -> str:
    """Format detailed status information for display."""
    output = []
    output.append("=" * 60)
    output.append("🔧 PIKA-PIKA STATUS MONITOR")
    output.append("=" * 60)
    output.append("")
    
    # Execution Mode
    execution_mode = get_execution_mode(processes)
    mode_display = {
        "multiprocessing": "🔄 Multiprocessing Mode (python -m pika.main)",
        "single_process": "⚡ Single Process Mode (uvicorn pika.app:app)",
        "none": "❌ Not Running"
    }
    output.append(f"EXECUTION MODE: {mode_display[execution_mode]}")
    output.append("")
    
    # Process Status
    output.append("🔄 PROCESS STATUS:")
    output.append("")
    
    if 'error' in processes:
        output.append(f"❌ Process check error: {processes['error']}")
    else:
        for process_name, status in processes.items():
            if process_name == 'error' or not isinstance(status, dict):
                continue
                
            display_name = process_name.replace('_', ' ').title()
            if status['running']:
                pids_str = ', '.join(map(str, status['pids']))
                output.append(f"✅ {display_name}: Running (PID: {pids_str})")
                # Show command line for debugging
                if status['cmdlines']:
                    for cmdline in status['cmdlines'][:1]:  # Show first cmdline only
                        short_cmd = cmdline[:80] + "..." if len(cmdline) > 80 else cmdline
                        output.append(f"   Command: {short_cmd}")
            else:
                output.append(f"❌ {display_name}: Not running")
    
    output.append("")
    
    # Shared Memory Status (only if multiprocessing mode)
    if execution_mode == "multiprocessing":
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
    
    # Overall Status
    any_running = is_any_pika_running(processes)
    shared_memory_ok = all(
        status.get('available', False) 
        for key, status in shared_memory_status.items() 
        if key != 'config_error'
    )
    
    if execution_mode == "multiprocessing":
        if any_running and shared_memory_ok:
            output.append("🎉 SYSTEM STATUS: Multiprocessing system is fully operational!")
        elif any_running:
            output.append("⚠️  SYSTEM STATUS: Processes running, but shared memory issues detected")
        else:
            output.append("❌ SYSTEM STATUS: Multiprocessing system not running")
    elif execution_mode == "single_process":
        output.append("🎉 SYSTEM STATUS: Single process mode is running!")
    else:
        output.append("❌ SYSTEM STATUS: No pika-pika processes detected")
    
    output.append("")
    output.append("=" * 60)
    
    return "\n".join(output)


def format_json_status(processes: Dict[str, Any], shared_memory_status: Dict[str, Any]) -> str:
    """Format status as JSON for automation."""
    execution_mode = get_execution_mode(processes)
    any_running = is_any_pika_running(processes)
    
    status_data = {
        "timestamp": time.time(),
        "execution_mode": execution_mode,
        "running": any_running,
        "processes": processes,
        "shared_memory": shared_memory_status if execution_mode == "multiprocessing" else None
    }
    
    return json.dumps(status_data, indent=2, default=str)


def simple_check_output(processes: Dict[str, Any]) -> Tuple[str, int]:
    """Simple check output for Makefile usage."""
    any_running = is_any_pika_running(processes)
    
    if any_running:
        execution_mode = get_execution_mode(processes)
        if execution_mode == "multiprocessing":
            message = "pika-pika multiprocessing system is running"
        elif execution_mode == "single_process":
            message = "pika-pika single process is running"
        else:
            message = "pika-pika application is running"
        return message, 1  # Exit code 1 means running (for Makefile logic)
    else:
        return "No pika-pika application found running", 0  # Exit code 0 means not running


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Pika-pika Status Monitor")
    parser.add_argument("--check", action="store_true", 
                       help="Simple running check (exit codes for Makefile)")
    parser.add_argument("--json", action="store_true",
                       help="Output status as JSON")
    
    args = parser.parse_args()
    
    try:
        # Check process status
        processes = check_pika_processes()
        
        # Simple check mode (for Makefile compatibility)
        if args.check:
            message, exit_code = simple_check_output(processes)
            print(message)
            return exit_code
        
        # Check shared memory status (only needed for detailed output)
        shared_memory_status = check_shared_memory_status()
        
        # JSON output mode
        if args.json:
            json_output = format_json_status(processes, shared_memory_status)
            print(json_output)
            return 0
        
        # Default: detailed status output
        print("Checking Pika-pika status...")
        print()
        
        status_output = format_detailed_status(processes, shared_memory_status)
        print(status_output)
        
        # Return appropriate exit code for detailed mode
        any_running = is_any_pika_running(processes)
        execution_mode = get_execution_mode(processes)
        
        if execution_mode == "multiprocessing":
            shared_memory_ok = all(
                status.get('available', False) 
                for key, status in shared_memory_status.items() 
                if key != 'config_error'
            )
            return 0 if (any_running and shared_memory_ok) else 1
        elif execution_mode == "single_process":
            return 0 if any_running else 1
        else:
            return 1  # Not running
            
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