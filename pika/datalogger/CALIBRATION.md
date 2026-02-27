# Adaptive Voltage Calibration

## Overview

The datalogger now features **automatic voltage calibration** that eliminates the need to manually configure the `transformer_ratio` parameter. The system learns the correct scaling factor during startup by assuming steady-state mains voltage should be 120V RMS (US standard).

## How It Works

### Learning Phase (First ~16 seconds)

1. **Measure ADC Voltage**: During the first 1000 AC cycles (~16s at 60Hz), the system measures the RMS voltage at the ADC input (after the ZMPT101B sensor)

2. **Auto-Calculate Ratio**: When learning completes, the system calculates:
   ```
   transformer_ratio = 120V / measured_adc_rms
   ```

3. **Set Nominal Voltage**: The nominal voltage is set to exactly 120V, which becomes the baseline for anomaly detection

### Example

If your ZMPT101B outputs 0.9V RMS when measuring 120V mains:
```
transformer_ratio = 120 / 0.9 = 133.33
```

All subsequent voltage readings are scaled by this learned ratio.

## Benefits

- **No Manual Calibration**: Adjust the ZMPT101B potentiometer to avoid clipping without worrying about exact voltage levels
- **Adaptive**: System automatically compensates for sensor variations, component tolerances, and gain adjustments
- **Relative Detection**: Anomaly detection is based on deviations from the learned steady-state, not absolute voltage values
- **Robust**: If ADC measurement is too low (< 1mV), falls back to config file `transformer_ratio`

## Configuration

The `transformer_ratio` in `config/logger.yaml` is now used only as a fallback. The system will override it during startup:

```yaml
sensor:
  transformer_ratio: 120     # Fallback value only; auto-calibrated on startup
```

## Startup Messages

Watch for these log messages during startup:

```
[Detector] Init: rate=10000 Hz, rms_window=500 samples (30 cycles), 
           learn=16667 samples (1000 cycles), adc_vref=5.0, 
           initial_ratio=120.0 (will auto-calibrate)

[Detector] Auto-calibration complete:
  Measured ADC RMS: 0.9000 V
  Target Mains: 120.0 V
  Learned transformer_ratio: 133.33
  Nominal VRMS set to: 120.0 V
```

## Anomaly Detection

After calibration, all anomaly thresholds are calculated relative to the 120V baseline:

- **SAG**: < 108V (120V - 10%)
- **SWELL**: > 132V (120V + 10%)

This ensures consistent detection regardless of ZMPT101B gain settings.

## Regional Adaptation

For 50Hz regions or different nominal voltages, modify the target in `anomaly_detector.c`:

```c
const float TARGET_MAINS_VRMS = 120.0f;  // Change to 230.0f for EU
```

## Troubleshooting

**Warning: ADC RMS too low**
- Check ZMPT101B power supply (VCC)
- Verify AC mains connection
- Ensure BUSY/CONVST signals are working
- Check for clipping (signal should swing positive and negative)

**Learned ratio seems wrong**
- Verify mains voltage is actually ~120V with a multimeter
- Check for noise or interference during learning phase
- Increase `learn_cycles` in config for more stable measurement
