# Design Document: BeagleBone Black Project Shell

## Overview

The BeagleBone Black project shell establishes a monorepo structure for a multi-phase data acquisition system. This design focuses exclusively on creating the directory layout, build orchestration system, and documentation skeleton. No implementation logic is included - this is purely structural scaffolding to support future development phases.

The project consists of three main components:
1. **PRU Firmware** - Real-time data capture from AD7606 ADC
2. **Data Logger** - Linux userspace application for logging and anomaly detection
3. **Web Application** - FastAPI-based visualization interface

The build system uses Make for orchestration, with a top-level Makefile delegating to component-specific Makefiles.

## Architecture

### High-Level Structure

```
pika/
├── Makefile                # Top-level orchestrator
├── README.md               # Project documentation
├── pru/                    # PRU firmware component
│   ├── Makefile
│   ├── include/
│   ├── src/
│   └── firmware/
├── datalogger/             # Linux data logger component
│   ├── Makefile
│   ├── src/
│   ├── config/
│   └── data/
├── webapp/                 # FastAPI web application component
│   ├── Makefile
│   ├── app/
│   ├── static/
│   └── templates/
├── overlays/               # Device tree overlays
│   └── ad7606-pru0.dts
└── docs/                   # Project documentation
    ├── architecture.md
    ├── memory-map.md
    └── bringup-checklist.md
```

### Component Separation

The architecture enforces clear separation of concerns:

- **pru/**: Contains all PRU-related code, headers, and compiled firmware binaries
- **datalogger/**: Contains Linux userspace application code, configuration files, and data storage
- **webapp/**: Contains web application code, static assets, and HTML templates
- **overlays/**: Contains device tree overlay files for hardware configuration
- **docs/**: Contains architecture documentation and setup guides

### Build System Architecture

The build system uses a hierarchical delegation pattern:

1. **Top-Level Makefile**: Provides high-level targets (all, pru, datalogger, web, clean) and delegates to subprojects
2. **Subproject Makefiles**: Handle component-specific build logic (currently placeholders)
3. **Extensibility**: New targets can be added to the top-level Makefile without modifying subproject structure

## Components and Interfaces

### Top-Level Makefile

**Purpose**: Orchestrate builds across all subprojects

**Targets**:
- `all`: Build all components (delegates to pru, datalogger, webapp)
- `pru`: Build PRU firmware (delegates to pru/Makefile)
- `datalogger`: Build data logger (delegates to datalogger/Makefile)
- `web`: Build web application (delegates to webapp/Makefile)
- `clean`: Clean all build artifacts (delegates to all subproject Makefiles)

**Implementation Pattern**:
```makefile
.PHONY: all pru datalogger web clean

all: pru datalogger web

pru:
	$(MAKE) -C pru

datalogger:
	$(MAKE) -C datalogger

web:
	$(MAKE) -C webapp

clean:
	$(MAKE) -C pru clean
	$(MAKE) -C datalogger clean
	$(MAKE) -C webapp clean
```

### Subproject Makefiles

**Purpose**: Provide component-specific build logic

**Current Implementation**: Placeholder targets that print status messages

**Future Extension Points**:
- PRU Makefile: Will compile C code to PRU firmware binaries
- Data Logger Makefile: Will build Linux application (likely Python or C)
- Web Application Makefile: Will set up Python virtual environment and dependencies

**Placeholder Pattern**:
```makefile
.PHONY: all clean

all:
	@echo "Building [component]..."
	@echo "No build steps defined yet."

clean:
	@echo "Cleaning [component]..."
	@echo "No clean steps defined yet."
```

### Documentation Files

**README.md**:
- Project overview and purpose
- Directory structure explanation
- Build instructions
- Component descriptions
- Future development roadmap

**docs/architecture.md**:
- Placeholder for detailed system architecture
- Will document PRU/Linux communication mechanisms
- Will document data flow between components

**docs/memory-map.md**:
- Placeholder for PRU shared memory layout
- Will document memory regions for PRU/Linux data exchange

**docs/bringup-checklist.md**:
- Placeholder for hardware setup procedures
- Will document BeagleBone Black configuration steps
- Will document testing and validation procedures

### Device Tree Overlay

**overlays/ad7606-pru0.dts**:
- Placeholder device tree overlay file
- Will configure PRU0 for AD7606 interface
- Will define pin multiplexing and hardware resources

**Placeholder Content**:
```
// Device Tree Overlay for AD7606 with PRU0
// TODO: Define pin configuration, PRU resource allocation, and hardware setup
```

## Data Models

This phase does not define data models, as no implementation code is included. Future phases will define:

- PRU data structures for ADC samples
- Data logger structures for time-series data
- Web application models for visualization data

## Correctness Properties


*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Since this project shell is primarily about creating a static directory structure and build system, most requirements are specific examples rather than universal properties. However, we can identify a few properties that should hold across multiple instances:

**Property 1: Subproject Makefile Execution**

*For any* subproject Makefile (pru/Makefile, datalogger/Makefile, webapp/Makefile), invoking "make" directly in that directory should execute without errors and produce output indicating the build status.

**Validates: Requirements 3.4**

**Property 2: Naming Convention Consistency**

*For any* directory or file created by the project shell, the name should follow consistent conventions (lowercase with hyphens or underscores, no spaces or special characters).

**Validates: Requirements 6.4**

**Note on Testing Approach**: Most requirements in this spec are specific structural examples (e.g., "directory X exists", "file Y contains Z"). These are best validated through example-based tests that verify the exact structure was created correctly. The properties above capture the few universal rules that apply across multiple instances.

## Error Handling

Since this phase creates only static files and directories, error handling is minimal:

**File System Errors**:
- If directories cannot be created due to permissions, the setup should fail with a clear error message
- If files cannot be written, the setup should fail with a clear error message

**Makefile Errors**:
- If Make is not installed, attempting to run Makefiles should produce a clear error
- If subproject Makefiles are missing, the top-level Makefile should fail gracefully with an informative message

**Future Considerations**:
- Future phases will need robust error handling for PRU firmware loading
- Future phases will need error handling for data logger failures
- Future phases will need error handling for web application startup

## Testing Strategy

### Dual Testing Approach

This project uses both unit tests and property-based tests to ensure comprehensive coverage:

- **Unit tests**: Verify specific directory structure, file existence, and Makefile content
- **Property tests**: Verify universal properties across all subproject Makefiles and naming conventions

### Unit Testing

Unit tests will focus on:

1. **Directory Structure Validation**:
   - Verify root "pika" directory exists
   - Verify all required subdirectories exist (pru/, datalogger/, webapp/, overlays/, docs/)
   - Verify component-specific subdirectories exist (pru/include/, pru/src/, etc.)

2. **File Existence Validation**:
   - Verify top-level Makefile exists
   - Verify README.md exists
   - Verify all subproject Makefiles exist
   - Verify documentation files exist (architecture.md, memory-map.md, bringup-checklist.md)
   - Verify device tree overlay file exists (ad7606-pru0.dts)

3. **Content Validation**:
   - Verify README.md contains project description, directory structure, and build instructions
   - Verify top-level Makefile contains required targets (all, pru, datalogger, web, clean)
   - Verify device tree overlay contains placeholder comment
   - Verify source directories are empty (no implementation code)

4. **Makefile Delegation**:
   - Verify "make pru" invokes pru/Makefile
   - Verify "make datalogger" invokes datalogger/Makefile
   - Verify "make web" invokes webapp/Makefile
   - Verify "make clean" invokes clean in all subproject Makefiles

### Property-Based Testing

Property tests will use a property-based testing library (e.g., Hypothesis for Python, QuickCheck for Haskell, or fast-check for JavaScript/TypeScript) configured with a minimum of 100 iterations per test.

**Property Test 1: Subproject Makefile Execution**
- **Tag**: Feature: bbb-project-shell, Property 1: For any subproject Makefile, invoking "make" directly should execute without errors
- **Test**: For each subproject directory (pru, datalogger, webapp), change to that directory and run "make", verify exit code is 0

**Property Test 2: Naming Convention Consistency**
- **Tag**: Feature: bbb-project-shell, Property 2: For any directory or file created, names should follow consistent conventions
- **Test**: For all created directories and files, verify names match pattern: lowercase, hyphens/underscores only, no spaces or special characters

### Testing Implementation

Since this is a project shell setup, tests will likely be implemented as:
- **Shell scripts**: For directory structure and file existence validation
- **Python tests**: Using pytest for more complex validation logic
- **Make targets**: A "test" target in the top-level Makefile to run all validation

The testing strategy will be refined in the implementation phase based on the chosen testing framework.
