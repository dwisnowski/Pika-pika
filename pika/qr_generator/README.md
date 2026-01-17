# QR Code Generator Package

This package provides a clean, modular system for generating QR codes with various configuration options and output formats.

## Components

### QRCodeGenerator (`generator.py`)
Main class for QR code generation with methods:
- `create_qr_code()` - Create basic QR code
- `scale_qr_to_fit()` - Scale QR to fit dimensions
- `create_background()` - Create background image
- `center_qr_on_background()` - Center QR on background
- `generate_qr_image()` - Complete QR with background
- `generate_simple_qr()` - Simple QR without background

### Configuration (`config.py`)
Centralized configuration:
- `QRDefaults` - Default generation settings
- `QRColors` - Standard color definitions
- `DisplaySizes` - Common display dimensions

## Usage

### Basic Usage
```python
from pika.qr_generator import QRCodeGenerator

# Create generator with default settings
generator = QRCodeGenerator()

# Generate QR code with background
qr_image = generator.generate_qr_image(
    data="https://example.com",
    output_width=240,
    output_height=320
)
```

### Custom Configuration
```python
from pika.qr_generator import QRCodeGenerator

# Create generator with custom settings
generator = QRCodeGenerator(
    border=3,
    box_size=10,
    margin=30,
    text_offset_y=-20
)

qr_image = generator.generate_qr_image(
    data="https://example.com",
    output_width=320,
    output_height=240,
    background_color=(240, 240, 240)  # Light gray
)
```

### Simple QR Code
```python
# Generate simple QR without background
simple_qr = generator.generate_simple_qr(
    data="https://example.com",
    size=200
)
```

### Backward Compatibility
```python
from pika.qr_generator import make_qr_image

# Same function signature as original
qr_image = make_qr_image(
    url="https://example.com",
    out_w=240,
    out_h=320
)
```

## Benefits

1. **Single Responsibility**: Focused solely on QR code generation
2. **Configurable**: Customizable borders, sizes, colors, and positioning
3. **Reusable**: Can be used independently of display system
4. **Testable**: Each method can be tested in isolation
5. **Extensible**: Easy to add new QR code features
6. **Backward Compatible**: Drop-in replacement for original function

## Migration Notes

The original `make_qr_image` function from `display_qr.py` can be replaced with:
```python
# Old
from pika.display_qr import make_qr_image

# New  
from pika.qr_generator import make_qr_image
```

Or use the more flexible `QRCodeGenerator` class for advanced usage.
