# Requirements Document

## Introduction

This specification defines the requirements for extracting the datalogger from the current single-process FastAPI application into a separate process architecture. The goal is to achieve true multiprocessing on the Raspberry Pi 2's quad-core CPU while maintaining all existing functionality including high-frequency sampling, real-time WebSocket streaming, event detection, and hardware integration.

## Glossary

- **Datalogger_Process**: Dedicated process responsible for high-frequency ADC sampling and data persistence
- **Event_Logger_Process**: Dedicated process for anomaly detection, analysis, and event logging
- **FastAPI_Process**: Process running the web server, API endpoints, and application logic
- **WebSocket_Handler**: Component within FastAPI process managing real-time data streaming
- **Shared_Memory**: Inter-process communication mechanism using memory-mapped data structures
- **Display_Manager**: Hardware display controller integrated with the datalogger
- **Sample_Callback**: Function interface for real-time data notifications
- **Analysis_Metrics**: Real-time computed statistics (RMS, frequency, sags/swells)
- **Highlights_Manager**: Anomaly detection and event logging subsystem

## Requirements

### Requirement 1: Process Separation

**User Story:** As a system administrator, I want the datalogger to run in a separate process, so that high-frequency sampling continues uninterrupted even if the web server crashes.

#### Acceptance Criteria

1. WHEN the system starts, THE System SHALL create four distinct processes: Datalogger_Process, Event_Logger_Process, FastAPI_Process, and WebSocket_Handler
2. WHEN the FastAPI_Process crashes or restarts, THE Datalogger_Process SHALL continue sampling without interruption
3. WHEN the Datalogger_Process encounters an error, THE FastAPI_Process SHALL continue serving web requests
4. THE System SHALL assign each process to dedicated CPU cores where possible on the Raspberry Pi 2

### Requirement 2: Shared Memory Communication

**User Story:** As a developer, I want efficient inter-process communication, so that real-time data can be shared between processes with minimal latency.

#### Acceptance Criteria

1. WHEN the Datalogger_Process generates a new sample, THE System SHALL write it to Shared_Memory within 1ms
2. WHEN the FastAPI_Process requests recent data, THE System SHALL read from Shared_Memory without blocking the Datalogger_Process
3. WHEN Analysis_Metrics are computed, THE System SHALL update them in Shared_Memory for WebSocket broadcasting
4. THE System SHALL use memory-mapped circular buffers for sample data storage
5. THE System SHALL implement lock-free data structures where possible to minimize contention

### Requirement 3: Data Persistence Continuity

**User Story:** As a power quality engineer, I want continuous data logging, so that no samples are lost during process transitions or failures.

#### Acceptance Criteria

1. WHEN the Datalogger_Process starts, THE System SHALL restore the last 30 seconds of data from disk to memory
2. WHEN the Datalogger_Process writes samples to CSV, THE System SHALL maintain the existing batch writing mechanism
3. WHEN daily log file rotation occurs, THE System SHALL continue sampling without interruption
4. WHEN the system shuts down gracefully, THE System SHALL flush all pending samples to disk
5. THE System SHALL maintain the existing file naming convention and CSV format

### Requirement 4: Real-time WebSocket Streaming

**User Story:** As a monitoring operator, I want real-time data visualization, so that I can observe power quality metrics as they occur.

#### Acceptance Criteria

1. WHEN new samples are available in Shared_Memory, THE WebSocket_Handler SHALL broadcast them to connected clients within 10ms
2. WHEN Analysis_Metrics are updated, THE System SHALL include them in WebSocket messages at 5Hz frequency
3. WHEN clients connect to the WebSocket endpoint, THE System SHALL send the last 5 seconds of data immediately
4. THE System SHALL maintain the existing WebSocket message format for client compatibility
5. WHEN the Datalogger_Process is unavailable, THE WebSocket_Handler SHALL continue serving cached data

### Requirement 5: Event Detection and Logging

**User Story:** As a power quality analyst, I want automated anomaly detection, so that significant events are captured and logged for analysis.

#### Acceptance Criteria

1. WHEN the Event_Logger_Process detects an anomaly, THE System SHALL log it to the highlights.json file
2. WHEN sags, swells, or frequency deviations occur, THE System SHALL compute and store event metadata
3. WHEN the FastAPI_Process requests highlights, THE System SHALL read from the current highlights file
4. THE System SHALL maintain the existing highlights data format and API compatibility
5. WHEN event detection parameters are updated, THE System SHALL apply them without restarting processes

### Requirement 6: Hardware Integration Preservation

**User Story:** As a system integrator, I want hardware components to continue working, so that the LCD display and ADC sampling remain functional.

#### Acceptance Criteria

1. WHEN the Datalogger_Process initializes, THE System SHALL configure the ADS1115 ADC with the specified sample rate
2. WHEN the Display_Manager starts, THE System SHALL render QR codes and real-time metrics on the LCD
3. WHEN demo mode is enabled, THE System SHALL use MockADC instead of hardware ADC
4. THE System SHALL maintain the existing hardware configuration via TOML files
5. WHEN hardware initialization fails, THE System SHALL fall back to simulation mode gracefully

### Requirement 7: Configuration Management

**User Story:** As a system administrator, I want centralized configuration, so that all processes use consistent settings.

#### Acceptance Criteria

1. WHEN the system starts, THE System SHALL load configuration from the existing config.toml file
2. WHEN sample rate is changed via API, THE System SHALL update the Datalogger_Process configuration
3. WHEN analysis parameters are modified, THE System SHALL notify the Event_Logger_Process
4. THE System SHALL maintain backward compatibility with existing configuration structure
5. WHEN configuration changes are made, THE System SHALL apply them without full system restart

### Requirement 8: Graceful Startup and Shutdown

**User Story:** As a system operator, I want reliable process lifecycle management, so that the system starts and stops cleanly.

#### Acceptance Criteria

1. WHEN the system starts, THE System SHALL initialize processes in the correct dependency order
2. WHEN a process fails to start, THE System SHALL log the error and attempt graceful degradation
3. WHEN shutdown is requested, THE System SHALL stop processes in reverse dependency order
4. WHEN a child process terminates unexpectedly, THE System SHALL attempt to restart it
5. THE System SHALL implement proper signal handling for SIGTERM and SIGINT

### Requirement 9: API Compatibility

**User Story:** As a web client developer, I want existing APIs to continue working, so that no client-side changes are required.

#### Acceptance Criteria

1. WHEN clients request recent data via /api/recent, THE System SHALL return data from Shared_Memory
2. WHEN clients request historical data via /api/range, THE System SHALL read from CSV files as before
3. WHEN clients request highlights via /api/highlights, THE System SHALL return current anomaly data
4. THE System SHALL maintain all existing API endpoints and response formats
5. WHEN configuration APIs are called, THE System SHALL update the appropriate process configurations

### Requirement 10: Performance Optimization

**User Story:** As a performance engineer, I want optimal CPU utilization, so that the Raspberry Pi 2's quad-core architecture is fully utilized.

#### Acceptance Criteria

1. WHEN the system is running, THE Datalogger_Process SHALL achieve consistent 100Hz sampling with minimal jitter
2. WHEN multiple processes are active, THE System SHALL distribute CPU load across available cores
3. WHEN memory usage is measured, THE System SHALL use no more than 50% of available RAM
4. THE System SHALL minimize context switching between processes during normal operation
5. WHEN system load is high, THE Datalogger_Process SHALL maintain sampling priority over other processes