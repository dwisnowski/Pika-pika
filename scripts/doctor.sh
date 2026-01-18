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
if ! command -v i2cdetect >/dev/null; then
    echo -e "${RED}[error]${NC} i2cdetect not found. Run 'sudo apt install i2c-tools'."
else
    # Run i2cdetect and capture output
    I2C_DATA=$(sudo i2cdetect -y 1 2>&1)
    echo "$I2C_DATA"
    
    # Validation: Look for address 0x48 (ADS1115 default)
    # i2cdetect output usually looks like "40: -- -- -- -- -- -- -- -- 48 -- -- --" 
    if echo "$I2C_DATA" | grep -q "48"; then
        echo -e "${GREEN}[pass]${NC} Found I2C device at address 0x48 (ADS1115 ADC)."
    else
        echo -e "${RED}[fail]${NC} No device found at address 0x48."
        echo -e "${YELLOW}------------------------------------------------------------"
        echo -e "HINT: ADS1115 ADC not detected."
        echo -e "1. Check Wiring: VCC, GND, SDA (Pin 3), SCL (Pin 5)."
        echo -e "2. Check Interface: Ensure I2C is enabled (sudo raspi-config)."
        echo -e "3. Check Power: Ensure the sensor module power LED is on."
        echo -e "------------------------------------------------------------${NC}"
    fi
fi

# 3. Check SPI
echo -e "\n${BLUE}[SPI Diagnostic]${NC}"
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
