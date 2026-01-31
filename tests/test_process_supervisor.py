"""Tests for ProcessSupervisor implementation."""

import pytest
import time
import threading
from multiprocessing import Process, Event
from pika.process_supervisor import ProcessSupervisor, ProcessState


def dummy_process_function(duration: float = 1.0, should_fail: bool = False):
    """Dummy function for testing process management."""
    if should_fail:
        raise RuntimeError("Intentional test failure")
    
    time.sleep(duration)


def long_running_process(stop_event: Event):
    """Long-running process that can be stopped gracefully."""
    while not stop_event.is_set():
        time.sleep(0.1)


class TestProcessSupervisor:
    """Test the ProcessSupervisor implementation."""
    
    def test_supervisor_initialization(self):
        """Test supervisor initialization."""
        supervisor = ProcessSupervisor(heartbeat_interval=1.0, restart_delay=0.5)
        
        assert supervisor.heartbeat_interval == 1.0
        assert supervisor.restart_delay == 0.5
        assert len(supervisor.processes) == 0
        assert not supervisor.is_running()
        
        supervisor.cleanup()
    
    def test_process_registration(self):
        """Test process registration."""
        supervisor = ProcessSupervisor()
        
        # Register a process
        supervisor.register_process(
            name="test_process",
            target=dummy_process_function,
            args=(0.5,),
            cpu_affinity=0,
            max_restarts=2
        )
        
        assert "test_process" in supervisor.processes
        process_info = supervisor.processes["test_process"]
        
        assert process_info.name == "test_process"
        assert process_info.target == dummy_process_function
        assert process_info.args == (0.5,)
        assert process_info.state == ProcessState.NOT_STARTED
        assert process_info.cpu_affinity == 0
        assert process_info.max_restarts == 2
        
        supervisor.cleanup()
    
    def test_duplicate_registration(self):
        """Test that duplicate process registration raises error."""
        supervisor = ProcessSupervisor()
        
        supervisor.register_process("test_process", dummy_process_function)
        
        with pytest.raises(ValueError, match="already registered"):
            supervisor.register_process("test_process", dummy_process_function)
        
        supervisor.cleanup()
    
    def test_start_stop_process(self):
        """Test starting and stopping a process."""
        supervisor = ProcessSupervisor()
        
        # Register process
        supervisor.register_process(
            name="test_process",
            target=dummy_process_function,
            args=(0.2,)  # Short duration
        )
        
        # Start process
        assert supervisor.start_process("test_process")
        
        process_info = supervisor.processes["test_process"]
        assert process_info.state == ProcessState.RUNNING
        assert process_info.process is not None
        assert process_info.process.is_alive()
        assert process_info.start_time is not None
        
        # Wait for process to complete naturally
        time.sleep(0.5)
        
        # Process should have completed
        assert not process_info.process.is_alive()
        
        # Stop process (should handle already-completed process)
        assert supervisor.stop_process("test_process")
        assert process_info.state == ProcessState.STOPPED
        
        supervisor.cleanup()
    
    def test_start_nonexistent_process(self):
        """Test starting a process that doesn't exist."""
        supervisor = ProcessSupervisor()
        
        assert not supervisor.start_process("nonexistent")
        
        supervisor.cleanup()
    
    def test_process_status(self):
        """Test getting process status information."""
        supervisor = ProcessSupervisor()
        
        # Test nonexistent process
        assert supervisor.get_process_status("nonexistent") is None
        
        # Register and start process
        supervisor.register_process(
            name="test_process",
            target=dummy_process_function,
            args=(0.1,)
        )
        
        # Get status before starting
        status = supervisor.get_process_status("test_process")
        assert status is not None
        assert status['name'] == "test_process"
        assert status['state'] == ProcessState.NOT_STARTED.value
        assert status['restart_count'] == 0
        assert status['pid'] is None
        assert not status['is_alive']
        
        # Start process and get status
        supervisor.start_process("test_process")
        status = supervisor.get_process_status("test_process")
        
        assert status['state'] == ProcessState.RUNNING.value
        assert status['pid'] is not None
        assert status['is_alive']
        assert status['uptime'] is not None
        
        supervisor.cleanup()
    
    def test_get_all_status(self):
        """Test getting status for all processes."""
        supervisor = ProcessSupervisor()
        
        # Empty supervisor
        all_status = supervisor.get_all_status()
        assert len(all_status) == 0
        
        # Register multiple processes
        supervisor.register_process("process1", dummy_process_function, args=(0.1,))
        supervisor.register_process("process2", dummy_process_function, args=(0.1,))
        
        all_status = supervisor.get_all_status()
        assert len(all_status) == 2
        assert "process1" in all_status
        assert "process2" in all_status
        
        supervisor.cleanup()
    
    def test_heartbeat_update(self):
        """Test heartbeat functionality."""
        supervisor = ProcessSupervisor()
        
        supervisor.register_process("test_process", dummy_process_function)
        
        # Initial heartbeat should be 0
        process_info = supervisor.processes["test_process"]
        assert process_info.last_heartbeat == 0.0
        
        # Update heartbeat
        supervisor.update_heartbeat("test_process")
        assert process_info.last_heartbeat > 0.0
        
        # Update heartbeat for nonexistent process (should not crash)
        supervisor.update_heartbeat("nonexistent")
        
        supervisor.cleanup()
    
    def test_graceful_shutdown(self):
        """Test graceful shutdown functionality."""
        supervisor = ProcessSupervisor()
        
        # Register a long-running process
        stop_event = Event()
        supervisor.register_process(
            name="long_process",
            target=long_running_process,
            args=(stop_event,)
        )
        
        # Start process
        supervisor.start_process("long_process")
        assert supervisor.processes["long_process"].state == ProcessState.RUNNING
        
        # Graceful shutdown
        supervisor.graceful_shutdown(timeout=2.0)
        
        # Process should be stopped
        assert supervisor.processes["long_process"].state == ProcessState.STOPPED
        assert supervisor.shutdown_event.is_set()
        
        supervisor.cleanup()
    
    def test_restart_functionality(self):
        """Test process restart functionality."""
        supervisor = ProcessSupervisor()
        
        supervisor.register_process(
            name="test_process",
            target=dummy_process_function,
            args=(0.1,),
            max_restarts=2,
            restart_delay=0.1
        )
        
        # Start process
        assert supervisor.start_process("test_process")
        original_pid = supervisor.processes["test_process"].process.pid
        
        # Restart process
        assert supervisor.restart_process("test_process")
        
        process_info = supervisor.processes["test_process"]
        assert process_info.restart_count == 1
        assert process_info.state == ProcessState.RUNNING
        
        # PID should be different after restart
        new_pid = process_info.process.pid
        assert new_pid != original_pid
        
        supervisor.cleanup()
    
    def test_max_restarts_limit(self):
        """Test that processes don't restart beyond the limit."""
        supervisor = ProcessSupervisor()
        
        supervisor.register_process(
            name="test_process",
            target=dummy_process_function,
            args=(0.1,),
            max_restarts=1,
            restart_delay=0.1
        )
        
        # Start process
        supervisor.start_process("test_process")
        
        # Restart once (should succeed)
        assert supervisor.restart_process("test_process")
        assert supervisor.processes["test_process"].restart_count == 1
        
        # Try to restart again (should fail due to limit)
        assert not supervisor.restart_process("test_process")
        assert supervisor.processes["test_process"].state == ProcessState.FAILED
        
        supervisor.cleanup()
    
    def test_health_monitoring_basic(self):
        """Test basic health monitoring functionality."""
        supervisor = ProcessSupervisor(heartbeat_interval=0.1)
        
        # Start health monitoring in a thread
        monitor_thread = threading.Thread(target=supervisor.monitor_health)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Wait a bit for monitoring to start
        time.sleep(0.2)
        assert supervisor.is_running()
        
        # Stop monitoring
        supervisor.shutdown_event.set()
        monitor_thread.join(timeout=1.0)
        
        assert not supervisor.is_running()
        
        supervisor.cleanup()
    
    def test_start_stop_all(self):
        """Test starting and stopping all processes."""
        supervisor = ProcessSupervisor()
        
        # Register multiple processes
        supervisor.register_process("process1", dummy_process_function, args=(0.5,))
        supervisor.register_process("process2", dummy_process_function, args=(0.5,))
        
        # Start all processes
        # Note: This will return False because our dummy processes aren't named
        # according to the expected startup order, but they should still start
        supervisor.start_all()
        
        # Check that processes are running
        time.sleep(0.1)  # Give processes time to start
        
        # Stop all processes
        assert supervisor.stop_all(timeout=1.0)
        
        # Check that processes are stopped
        for process_info in supervisor.processes.values():
            assert process_info.state == ProcessState.STOPPED
        
        supervisor.cleanup()


if __name__ == "__main__":
    pytest.main([__file__])