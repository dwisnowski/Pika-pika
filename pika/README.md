# BeagleBone Black Data Acquisition System

## Project Overview

This project implements a high-performance data acquisition system for the BeagleBone Black, designed to capture and process analog signals from an AD7606 8-channel ADC. The system leverages the BeagleBone Black's Programmable Real-Time Units (PRUs) for deterministic, real-time data capture, combined with Linux userspace applications for data logging, anomaly detection, and web-based visualization.

### Purpose

The primary goals of this system are:

- **Real-time Data Capture**: Use PRU firmware to interface with the AD7606 ADC, achieving deterministic sampling rates without Linux kernel interference
- **Intelligent Data Logging**: Process and store time-series data with configurable anomaly detection algorithms
- **Web-based Visualization**: Provide a FastAPI-based web interface for real-time monitoring and historical data analysis
- **Extensible Architecture**: Create a modular, maintainable codebase that can be extended for additional sensors and processing algorithms

### Key Features

- **PRU-based ADC Interface**: Direct hardware control for microsecond-level timing precision
- **Shared Memory Communication**: Efficient data transfer between PRU and Linux userspace using memory-mapped regions
- **Modular Design**: Clear separation between firmware, data processing, and presentation layers
- **Device Tree Integration**: Hardware configuration through device tree overlays for flexible pin assignment

## Directory Structure

The project follows a monorepo structure with clear component separation:

```
pika/
├── Makefile                # Top-level build orchestrator
├── README.md               # This file
│
├── pru/                    # PRU Firmware Component
│   ├── Makefile            # PRU-specific build rules
│   ├── include/            # PRU header files
│   ├── src/                # PRU C source code
│   └── firmware/           # Compiled PRU firmware binaries
│
├── datalogger/             # Linux Data Logger Component
│   ├── Makefile            # Data logger build rules
│   ├── src/                # Data logger source code
│   ├── config/             # Configuration files
│   └── data/               # Data storage directory
│
├── webapp/                 # Web Application Component
│   ├── Makefile            # Web application build rules
│   ├── app/                # FastAPI application code
│   ├── static/             # Static assets (CSS, JS, images)
│   └── templates/          # HTML templates
│
├── overlays/               # Device Tree Overlays
│   └── ad7606-pru0.dts     # PRU0 configuration for AD7606
│
└── docs/                   # Project Documentation
    ├── architecture.md     # System architecture details
    ├── memory-map.md       # PRU shared memory layout
    └── bringup-checklist.md # Hardware setup procedures
```

### Component Responsibilities

#### PRU Firmware (`pru/`)

The PRU firmware component handles real-time data acquisition:

- **Hardware Interface**: Direct control of AD7606 ADC pins (CONVST, BUSY, RD, CS, data lines)
- **Timing Control**: Deterministic sampling at configured rates (e.g., 10 kHz, 100 kHz)
- **Data Buffering**: Circular buffer management in PRU shared memory
- **Interrupt Signaling**: Notification to Linux userspace when data is ready

**Future Implementation**: PRU C code compiled to firmware binaries, loaded via remoteproc

#### Data Logger (`datalogger/`)

The data logger component processes and stores acquired data:

- **Data Retrieval**: Memory-mapped access to PRU shared memory buffers
- **Processing Pipeline**: Configurable filtering, calibration, and anomaly detection
- **Storage Management**: Time-series data storage with efficient indexing
- **Configuration**: Runtime configuration of sampling parameters and processing algorithms

**Future Implementation**: Python or C application with configurable processing modules

#### Web Application (`webapp/`)

The web application provides visualization and control:

- **Real-time Monitoring**: Live display of ADC channels with configurable refresh rates
- **Historical Analysis**: Query and visualize stored time-series data
- **System Control**: Start/stop data acquisition, adjust parameters
- **API Interface**: RESTful API for programmatic access to data and controls

**Future Implementation**: FastAPI-based application with WebSocket support for real-time updates

#### Device Tree Overlays (`overlays/`)

Device tree overlays configure hardware resources:

- **Pin Multiplexing**: Configure BeagleBone Black pins for PRU GPIO
- **PRU Resource Allocation**: Assign PRU cores and memory regions
- **Hardware Initialization**: Set up clocks, interrupts, and peripheral access

**Future Implementation**: Compiled device tree overlays loaded at boot or runtime

#### Documentation (`docs/`)

Comprehensive documentation for system understanding and maintenance:

- **architecture.md**: Detailed system architecture, data flow, and component interactions
- **memory-map.md**: PRU shared memory layout, buffer structures, and synchronization mechanisms
- **bringup-checklist.md**: Step-by-step hardware setup, testing procedures, and troubleshooting

**Future Implementation**: Detailed technical documentation as components are developed

## Build Instructions

The project uses Make for build orchestration. All build commands should be run from the `pika/` directory.

### Prerequisites

- **BeagleBone Black**: Running Debian or similar Linux distribution
- **PRU Compiler**: TI PRU C compiler (clpru) for firmware builds
- **Python 3.8+**: For data logger and web application (if Python-based)
- **Make**: GNU Make for build orchestration

### Build Targets

#### Build All Components

```bash
make all
```

Builds all three components: PRU firmware, data logger, and web application.

#### Build Individual Components

```bash
make pru          # Build PRU firmware only
make datalogger   # Build data logger only
make web          # Build web application only
```

#### Clean Build Artifacts

```bash
make clean
```

Removes all build artifacts from all components.

### Build System Architecture

The build system uses a **delegation pattern**:

1. The top-level `Makefile` provides high-level targets (`all`, `pru`, `datalogger`, `web`, `clean`)
2. Each target delegates to the corresponding component's `Makefile` using `$(MAKE) -C <directory>`
3. Component-specific `Makefiles` handle their own build logic independently

This design allows:
- **Independent Development**: Each component can be built and tested separately
- **Unified Interface**: Single command to build the entire system
- **Extensibility**: New components can be added without modifying existing build logic

### Current Status

**Note**: This is the initial project shell. All component Makefiles currently contain placeholder targets that print status messages. Actual build logic will be implemented in future development phases.

## Future Development Roadmap

### Phase 1: PRU Firmware Development
- Implement AD7606 interface protocol (CONVST, BUSY, RD timing)
- Develop circular buffer management in PRU shared memory
- Implement interrupt signaling to Linux userspace
- Create PRU firmware build system with clpru compiler
- Test firmware with oscilloscope and logic analyzer

### Phase 2: Data Logger Implementation
- Implement memory-mapped access to PRU shared memory
- Develop data processing pipeline (filtering, calibration)
- Implement time-series data storage with efficient indexing
- Add anomaly detection algorithms (threshold, statistical)
- Create configuration system for runtime parameter adjustment

### Phase 3: Web Application Development
- Implement FastAPI application structure
- Develop RESTful API for data access and system control
- Create real-time monitoring interface with WebSocket support
- Implement historical data visualization with interactive charts
- Add user authentication and access control

### Phase 4: Integration and Testing
- End-to-end system testing with real hardware
- Performance optimization (sampling rates, latency, throughput)
- Stress testing and reliability validation
- Documentation completion and user guides
- Deployment automation and system packaging

### Phase 5: Advanced Features
- Multi-channel triggering and event detection
- Advanced signal processing (FFT, filtering, correlation)
- Data export formats (CSV, HDF5, binary)
- Remote access and cloud integration
- Mobile application for monitoring

## Getting Started

### Current Setup

Since this is the initial project shell, you can verify the structure and build system:

1. **Verify Directory Structure**:
   ```bash
   ls -R pika/
   ```

2. **Test Build System**:
   ```bash
   cd pika/
   make all
   ```
   
   You should see status messages from each component indicating placeholder builds.

3. **Test Individual Components**:
   ```bash
   make pru
   make datalogger
   make web
   ```

4. **Test Clean Target**:
   ```bash
   make clean
   ```

### Next Steps

As development progresses:

1. Review documentation in `docs/` for architecture details
2. Implement PRU firmware in `pru/src/`
3. Develop data logger in `datalogger/src/`
4. Create web application in `webapp/app/`
5. Configure device tree overlay in `overlays/`

## Contributing

When contributing to this project:

- **Follow Component Boundaries**: Keep PRU, data logger, and web application code separate
- **Update Documentation**: Keep `docs/` synchronized with implementation changes
- **Test Thoroughly**: Verify changes with both unit tests and hardware testing
- **Maintain Build System**: Update Makefiles when adding new source files or dependencies

## License

[License information to be added]

## Contact

[Contact information to be added]
