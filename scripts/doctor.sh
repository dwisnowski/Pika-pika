#!/usr/bin/env bash
# ============================================================================
# Pika-pika Hardware Doctor Script
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}[pika-pika] Starting hardware diagnosis...${NC}"

# 1. Check System Info
if [ -f "/proc/device-tree/model" ]; then
    MODEL=$(cat /proc/device-tree/model)
    echo -e "${GREEN}[System] Model:${NC} $MODEL"
else
    echo -e "${YELLOW}[System] Warning:${NC} Not running on a Raspberry Pi (or device-tree missing)"
fi

# 2. Check I2C
echo -e "\n${BLUE}[I2C Diagnostic]${NC}"

# Check raspi-config status for I2C
if command -v raspi-config >/dev/null; then
    if sudo raspi-config nonint get_i2c | grep -q "0"; then
        echo -e "${GREEN}[config]${NC} I2C interface is ENABLED in raspi-config."
    else
        echo -e "${RED}[config]${NC} I2C interface is DISABLED in raspi-config."
    fi
fi

if ! command -v i2cdetect >/dev/null; then
    echo -e "${RED}[error]${NC} i2cdetect not found. Run 'sudo apt install i2c-tools'."
else
    # Run i2cdetect and capture output
    I2C_DATA=$(sudo i2cdetect -y 1 2>&1)
    echo "$I2C_DATA"
    
    # Validation: Look for address 0x48 (ADS1115 default)
    if echo "$I2C_DATA" | grep -q "48"; then
        echo -e "${GREEN}[pass]${NC} Found I2C device at address 0x48 (ADS1115 ADC)."
    else
        echo -e "${RED}[fail]${NC} No device found at address 0x48."
        echo -e "${YELLOW}------------------------------------------------------------"
        echo -e "HINT: ADS1115 ADC not detected on the I2C bus."
        echo -e "1. Physical Wiring (Most Common):"
        echo -e "   - VCC: Connect to Pi Pin 1 (3.3V) or Pin 2 (5V)"
        echo -e "   - GND: Connect to Pi Pin 6 or 9 (Ground)"
        echo -e "   - SDA: Connect to Pi Pin 3 (GPIO 2)"
        echo -e "   - SCL: Connect to Pi Pin 5 (GPIO 3)"
        echo -e "2. Enable Interface:"
        echo -e "   - Run: sudo raspi-config nonint do_i2c 0"
        echo -e "3. Verify Power:"
        echo -e "   - Does the ADC module have a power LED? Is it on?"
        echo -e "   - Use a multimeter to check for VCC at the sensor pins."
        echo -e "4. Scan Manually:"
        echo -e "   - Run 'sudo i2cdetect -y 1' again. If empty, check connections."
        echo -e "------------------------------------------------------------${NC}"
    fi
fi

# 3. Check SPI
echo -e "\n${BLUE}[SPI Diagnostic]${NC}"

# Check raspi-config status for SPI
if command -v raspi-config >/dev/null; then
    if sudo raspi-config nonint get_spi | grep -q "0"; then
        echo -e "${GREEN}[config]${NC} SPI interface is ENABLED in raspi-config."
    else
        echo -e "${RED}[config]${NC} SPI interface is DISABLED in raspi-config."
    fi
fi

if ls /dev/spidev0.0 1> /dev/null 2>&1; then
    echo -e "${GREEN}[pass]${NC} SPI device /dev/spidev0.0 found."
    ls -l /dev/spidev*
else
    echo -e "${RED}[fail]${NC} SPI device /dev/spidev0.0 NOT found."
    echo -e "${YELLOW}------------------------------------------------------------"
    echo -e "HINT: SPI interface is required for the mini-display."
    echo -e "1. Run 'sudo raspi-config'."
    echo -e "2. Go to 'Interface Options' -> 'SPI' and enable it."
    echo -e "3. Reboot your Raspberry Pi."
    echo -e "------------------------------------------------------------${NC}"
fi

echo -e "\n${BLUE}[pika-pika] Diagnosis complete.${NC}"
