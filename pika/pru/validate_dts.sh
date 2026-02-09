#!/bin/bash
# Validation script for device tree overlay
# This script checks the syntax and structure of the device tree overlay

DTS_FILE="../overlays/ad7606-pru0.dts"

echo "Validating device tree overlay: $DTS_FILE"
echo "================================================"

# Check if file exists
if [ ! -f "$DTS_FILE" ]; then
    echo "ERROR: $DTS_FILE not found"
    exit 1
fi

echo "✓ File exists"

# Check for required sections
echo ""
echo "Checking required sections..."

grep -q "/dts-v1/;" "$DTS_FILE" && echo "✓ DTS version declaration found" || echo "✗ Missing /dts-v1/;"
grep -q "/plugin/;" "$DTS_FILE" && echo "✓ Plugin declaration found" || echo "✗ Missing /plugin/;"
grep -q "compatible.*beaglebone" "$DTS_FILE" && echo "✓ Compatible string found" || echo "✗ Missing compatible string"
grep -q "part-number.*BB-PRU0-AD7606" "$DTS_FILE" && echo "✓ Part number found" || echo "✗ Missing part-number"
grep -q "exclusive-use" "$DTS_FILE" && echo "✓ Exclusive use declaration found" || echo "✗ Missing exclusive-use"

# Check for required fragments
echo ""
echo "Checking fragments..."

grep -q "fragment@0" "$DTS_FILE" && echo "✓ Fragment 0 found (HDMI disable)" || echo "✗ Missing fragment@0"
grep -q "fragment@1" "$DTS_FILE" && echo "✓ Fragment 1 found (pin mux)" || echo "✗ Missing fragment@1"
grep -q "fragment@2" "$DTS_FILE" && echo "✓ Fragment 2 found (PRU enable)" || echo "✗ Missing fragment@2"

# Check HDMI disable
echo ""
echo "Checking HDMI disable..."

grep -q "target.*lcdc" "$DTS_FILE" && echo "✓ LCDC target found" || echo "✗ Missing lcdc target"
grep -q "status.*disabled" "$DTS_FILE" && echo "✓ Status disabled found" || echo "✗ Missing status = disabled"

# Check pin configurations
echo ""
echo "Checking pin configurations..."

# Count pin configurations
PIN_COUNT=$(grep -c "0x[0-9a-f]\+ 0x[0-9a-f]\+" "$DTS_FILE")
echo "  Found $PIN_COUNT pin configurations"

if [ "$PIN_COUNT" -ge 18 ]; then
    echo "✓ Sufficient pins configured (expected 18: 1 output + 17 inputs)"
else
    echo "✗ Insufficient pins configured (expected 18, found $PIN_COUNT)"
fi

# Check for CONVST output (P9.31)
grep -q "0x190 0x05" "$DTS_FILE" && echo "✓ CONVST output configured (P9.31)" || echo "✗ Missing CONVST configuration"

# Check for BUSY input (P9.29)
grep -q "0x194 0x26" "$DTS_FILE" && echo "✓ BUSY input configured (P9.29)" || echo "✗ Missing BUSY configuration"

# Check PRU subsystem
echo ""
echo "Checking PRU subsystem configuration..."

grep -q "target.*pruss" "$DTS_FILE" && echo "✓ PRUSS target found" || echo "✗ Missing pruss target"
grep -q "status.*okay" "$DTS_FILE" && echo "✓ Status okay found" || echo "✗ Missing status = okay"
grep -q "pinctrl-0" "$DTS_FILE" && echo "✓ Pin control reference found" || echo "✗ Missing pinctrl-0"

# Check for balanced braces
echo ""
echo "Checking syntax..."

OPEN_BRACES=$(grep -o "{" "$DTS_FILE" | wc -l)
CLOSE_BRACES=$(grep -o "}" "$DTS_FILE" | wc -l)

echo "  Open braces: $OPEN_BRACES"
echo "  Close braces: $CLOSE_BRACES"

if [ "$OPEN_BRACES" -eq "$CLOSE_BRACES" ]; then
    echo "✓ Braces balanced"
else
    echo "✗ Braces not balanced"
fi

# Check for balanced angle brackets
OPEN_ANGLES=$(grep -o "<" "$DTS_FILE" | wc -l)
CLOSE_ANGLES=$(grep -o ">" "$DTS_FILE" | wc -l)

echo "  Open angles: $OPEN_ANGLES"
echo "  Close angles: $CLOSE_ANGLES"

if [ "$OPEN_ANGLES" -eq "$CLOSE_ANGLES" ]; then
    echo "✓ Angle brackets balanced"
else
    echo "✗ Angle brackets not balanced"
fi

echo ""
echo "================================================"
echo "Validation complete!"
echo ""
echo "Note: This is a basic syntax check. Full validation requires"
echo "compilation with dtc (device tree compiler) on the target system."
