# Display Manager Package

This package provides a modular, clean architecture for managing SPI LCD displays in the Pika-pika project.

## Package Structure

```
display_manager/
├── __init__.py          # Package exports and public API
├── config.py            # Configuration constants (Colors, Layout, Fonts)
├── utils.py             # Utility functions and helpers
├── data_source.py       # Data retrieval components
├── renderer.py          # Display rendering logic
├── manager.py           # Main DisplayManager class
├── singleton.py         # Global instance management
└── README.md           # This file
```

## Components

### DisplayManager (`manager.py`)
Main orchestrator that coordinates all display operations:
- Manages display lifecycle (start/stop)
- Coordinates between data sources and renderer
- Handles threading and timing
- Provides main API interface

### DisplayRenderer (`renderer.py`)
Handles all drawing operations:
- QR code rendering
- Text positioning and drawing
- Layout management
- Font management

### Data Sources (`data_source.py`)
Modular data retrieval components:
- `VoltageDataSource`: Voltage readings from datalogger
- `AnomalyDataSource`: Anomaly counts from highlights file
- `NetworkDataSource`: Network information and IP detection

### Configuration (`config.py`)
Centralized configuration:
- `Colors`: RGB color constants
- `Layout`: Positioning and sizing constants
- `Fonts`: Font preferences and fallbacks
- `DisplaySettings`: Default values and timeouts

### Utilities (`utils.py`)
Common helper functions:
- Font caching and loading
- Text positioning calculations
- Platform detection
- Data formatting helpers

### Singleton (`singleton.py`)
Global instance management:
- Ensures only one DisplayManager runs
- Provides backward-compatible API
- Thread-safe instance management

## Usage

### New Code (Recommended)
```python
from pika.display_manager import DisplayManager, start_display, stop_display

# Using singleton functions (simple)
display = start_display(logger_obj, auto_ip=True)

# Using class directly (more control)
manager = DisplayManager(logger_obj, fps=10.0)
manager.start()

# Stop display
stop_display()
```

### Legacy Code (Backward Compatible)
```python
from pika.display_manager import DisplayManager, start_display, stop_display

# Same API as before - no changes needed
display = start_display(logger_obj)
```

## Benefits of Package Structure

1. **Single Responsibility**: Each module has one clear purpose
2. **Testability**: Components can be tested in isolation
3. **Maintainability**: Easier to locate and modify specific functionality
4. **Reusability**: Components can be reused in different contexts
5. **Extensibility**: Easy to add new data sources or rendering features
6. **Readability**: Smaller, focused files are easier to understand

## Migration Notes

- All existing code continues to work without changes
- New imports use the package structure for better organization
- Configuration constants are now properly namespaced
- Error handling and logging are more consistent across components
