# Implementation Plan: Datalogger Multiprocessing

## Overview

This implementation plan transforms the current single-process FastAPI application into a multiprocessing architecture optimized for the Raspberry Pi 2's quad-core CPU. The approach prioritizes incremental development with minimal testing overhead while ensuring core components are robust.

## Tasks

- [x] 1. Create ADC adapter interface and implementations
  - Create abstract ADC adapter base class with interface methods
  - Implement ADS1115Adapter using existing datalogger ADC code
  - Implement MockADCAdapter for simulation mode
  - Create ADC factory function for adapter selection
  - _Requirements: 6.1, 6.3, 6.5_

- [x] 1.1 Write property test for ADC adapter interface
  - **Property 11: Hardware Fallback Behavior**
  - **Validates: Requirements 6.5**

- [ ] 2. Implement shared memory data structures
  - [x] 2.1 Create SharedSampleBuffer with circular buffer behavior
    - Implement memory-mapped circular buffer using SharedMemory
    - Add atomic write operations for sample data
    - Implement lock-free read operations for recent data access
    - _Requirements: 2.1, 2.4, 2.5_

  - [x] 2.2 Write property test for circular buffer behavior
    - **Property 3: Circular Buffer Behavior**
    - **Validates: Requirements 2.4**

  - [x] 2.3 Create SharedAnalysisBuffer for metrics storage
    - Implement JSON-serialized metrics storage in shared memory
    - Add thread-safe update and read operations
    - Include timestamp tracking for update frequency control
    - _Requirements: 2.3, 4.2_

  - [x] 2.4 Create SharedConfigBuffer for configuration synchronization
    - Implement versioned configuration storage
    - Add atomic configuration update operations
    - Include change detection mechanisms
    - _Requirements: 7.2, 7.3, 7.5_

- [x] 2.5 Write property test for non-blocking memory access
  - **Property 4: Non-blocking Memory Access**
  - **Validates: Requirements 2.2**

- [-] 3. Create process supervisor and management system
  - [x] 3.1 Implement ProcessSupervisor class
    - Create process lifecycle management (start, stop, restart)
    - Implement health monitoring with heartbeat checks
    - Add graceful shutdown coordination
    - Include CPU core affinity assignment
    - _Requirements: 1.1, 1.4, 8.1, 8.3, 8.4_

  - [x] 3.2 Write property test for process supervision
    - **Property 12: Process Supervision and Recovery**
    - **Validates: Requirements 8.2, 8.4**

  - [x] 3.3 Implement signal handling for graceful shutdown
    - Add SIGTERM and SIGINT handlers
    - Coordinate shutdown sequence across processes
    - Ensure proper cleanup of shared memory resources
    - _Requirements: 8.5_

- [x] 4. Checkpoint - Verify core infrastructure
  - Ensure shared memory structures work correctly
  - Verify process supervisor can start and stop processes
  - Test ADC adapter pattern with both real and mock hardware
  - Ask the user if questions arise.

- [x] 5. Extract datalogger into separate process
  - [x] 5.1 Create DataloggerProcess class
    - Move existing sampling logic to separate process
    - Integrate ADC adapter pattern
    - Implement shared memory buffer writing
    - Preserve existing CSV batch writing mechanism
    - _Requirements: 1.1, 3.2, 3.3, 3.5_

  - [x] 5.2 Implement data restoration from disk on startup
    - Load last 30 seconds of data into shared memory buffer
    - Maintain existing tail_from_disk functionality
    - _Requirements: 3.1_

  - [x] 5.3 Integrate display manager with datalogger process
    - Move display manager initialization to datalogger process
    - Maintain LCD QR code and metrics display
    - _Requirements: 6.2_

- [x] 5.4 Write property test for data persistence continuity
  - **Property 5: Data Persistence Continuity**
  - **Validates: Requirements 3.2, 3.3**

- [x] 6. Create event logger process
  - [x] 6.1 Extract analysis logic to EventLoggerProcess
    - Move StreamAnalyzer to separate process
    - Read samples from shared memory buffer
    - Write analysis metrics to SharedAnalysisBuffer
    - _Requirements: 5.1, 5.2_

  - [x] 6.2 Implement highlights file management
    - Maintain existing highlights.json format
    - Preserve anomaly detection and event logging
    - _Requirements: 5.4_

  - [x] 6.3 Add dynamic configuration support
    - Monitor SharedConfigBuffer for analysis parameter changes
    - Apply configuration updates without process restart
    - _Requirements: 5.5_

- [x] 7. Modify FastAPI process for multiprocessing
  - [x] 7.1 Update API endpoints to use shared memory
    - Modify /api/recent to read from SharedSampleBuffer
    - Update /api/highlights to read from highlights file
    - Preserve /api/range to use existing CSV file reading
    - _Requirements: 9.1, 9.2, 9.3_

  - [x] 7.2 Implement configuration API updates
    - Update sample rate API to write to SharedConfigBuffer
    - Add analysis parameter update endpoints
    - Ensure configuration changes propagate to appropriate processes
    - _Requirements: 9.5_

  - [x] 7.3 Remove datalogger initialization from FastAPI startup
    - Remove direct datalogger instantiation
    - Remove sample callback registration
    - Keep WebSocket manager initialization
    - _Requirements: 1.1_

- [x] 7.4 Write property test for API backward compatibility
  - **Property 10: API Backward Compatibility**
  - **Validates: Requirements 9.1, 9.2, 9.3, 9.4**

- [x] 8. Update WebSocket handler for shared memory
  - [x] 8.1 Modify ConnectionManager to read from shared memory
    - Update sample broadcasting to read from SharedSampleBuffer
    - Modify analysis metrics inclusion from SharedAnalysisBuffer
    - Maintain existing WebSocket message format
    - _Requirements: 4.1, 4.4_

  - [x] 8.2 Implement graceful degradation for missing datalogger
    - Continue serving cached data when datalogger unavailable
    - Add connection status indicators
    - _Requirements: 4.5_

  - [x] 8.3 Preserve initial data delivery on connection
    - Send last 5 seconds of data to new WebSocket connections
    - Maintain existing connection lifecycle
    - _Requirements: 4.3_

- [x] 9. Checkpoint - Test multiprocessing integration
  - Verify all processes start and communicate correctly
  - Test WebSocket streaming with shared memory data
  - Verify API endpoints return correct data
  - Test graceful shutdown sequence
  - Ask the user if questions arise.

- [x] 10. Create main application entry point
  - [x] 10.1 Create multiprocessing main application
    - Initialize shared memory structures
    - Start all processes in correct dependency order
    - Implement process supervision loop
    - _Requirements: 8.1_

  - [x] 10.2 Update existing app.py to use process supervisor
    - Replace direct datalogger usage with process supervisor
    - Maintain existing FastAPI configuration
    - Preserve uvicorn integration
    - _Requirements: 1.1_

  - [x] 10.3 Add configuration loading and validation
    - Load config.toml at startup
    - Validate configuration before process startup
    - Initialize SharedConfigBuffer with loaded configuration
    - _Requirements: 7.1, 7.4_

- [x] 10.4 Write property test for configuration propagation
  - **Property 9: Configuration Propagation**
  - **Validates: Requirements 7.2, 7.3, 7.5, 9.5**

- [x] 11. Final integration and cleanup
  - [x] 11.1 Test hardware integration with new architecture
    - Verify ADS1115 ADC works with datalogger process
    - Test LCD display functionality
    - Validate demo mode operation
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 11.2 Implement error handling and logging
    - Add comprehensive error logging across all processes
    - Implement process crash detection and recovery
    - Add shared memory error handling
    - _Requirements: 8.2_

  - [x] 11.3 Optimize performance and resource usage
    - Set appropriate process priorities
    - Configure CPU core affinity
    - Monitor memory usage and optimize buffers
    - _Requirements: 10.1, 10.2, 10.3_

- [x] 12. Final checkpoint - Complete system validation
  - Run extended testing with real hardware
  - Verify all existing functionality is preserved
  - Test system stability under load
  - Validate performance improvements
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with property tests validate universal correctness properties
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation and early problem detection
- The ADC adapter pattern enables future hardware migration to AD7606
- Minimal testing approach focuses on core components most likely to fail
- Property tests validate universal correctness properties across all inputs
- Integration testing relies primarily on manual verification for rapid iteration