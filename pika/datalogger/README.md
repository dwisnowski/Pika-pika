# Pika Linux Datalogger

The Pika Datalogger is a high-performance Linux userspace application responsible for consuming high-speed ADC data from the PRU, performing real-time signal processing, and storing events and decimated data to disk.

## Architecture Overview

The system follows a multi-threaded, zero-copy architecture designed to handle up to 180 kSPS without dropping samples.

```text
[ PRU (Real-time) ]          [ Linux Datalogger (ARM) ]
+----------------+          +-----------------------------------------+
|   AD7606 ADC   |          |                                         |
+-------+--------+          |  +-----------------------------------+  |
        |                   |  |      Shared DDR Ring Buffer       |  |
        v                   |  +-----------------+-----------------+  |
+-------+--------+          |                    |                    |
|  PRU Firmware  +----------|--------------------+  (Zero-copy Read)  |
+----------------+          |                    v                    |
        |                   |          +------------------+           |
        |  (DMA / IO)       |          |   Reader Thread  |           |
        +-------------------+          +---------+--------+           |
                               |                   |                  |
                               |          (Lock-free Buffer)          |
                               |                   v                  |
                               |          +------------------+        |
                               |          | Processor Thread |        |
                               |          +----+----+----+---+        |
                               |               |    |    |            |
                               |        +------+    |    +------+     |
                               |        v           v           v     |
                               |   +---------+ +---------+ +---------+ |
                               |   | Decimat | | Anomaly | | Event   | |
                               |   |  -or    | | Detect  | | Manager | |
                               |   +----+----+ +----+----+ +----+----+ |
                               |        |           |           |     |
                               |        +-----------+-----------+     |
                               |                    v                 |
                               |          +------------------+        |
                               |          |    RAM Buffers   |        |
                               |          +---------+--------+        |
                               |                    |                 |
                               |          +---------v--------+        |
                               |          |   Writer Thread  |        |
                               |          +---------+--------+        |
                               +--------------------|-----------------+
                                                    v
                                          [[ On-Disk Storage ]]
```

## Core Components

### 1. Reader Thread (`src/shm_reader.c`)
- Maps `/dev/mem` for **PRU Shared RAM** (control header at `0x4A310000`) and the **DDR sample ring** (`0x9C000000`, 1 MiB carve-out; requires `mem=448M` or equivalent).
- Tracks progress via `sample_count`, validates `flags == 0xAA55AA55`.
- Drains all completed blocks each cycle into a lock-free SPSC ring (100 µs idle poll).

### 2. Processing Thread
- Reconstructs per-sample times from each block’s `timestamp_cycles` + measured `period_cycles` (PRU CCNT is authoritative; YAML rate is pacing intent / fallback).
- **Decimator (`src/decimator.c`)**: Downsamples for continuous overview on disk.
- **Anomaly Detector (`src/anomaly_detector.c`)**: Detects power-quality events (Sag, Swell, Spike, Dip).
- **Event Manager (`src/event_window.c`)**: Pre/post hi-fidelity capture around anomalies only (no full-rate continuous archive).

### 3. Writer (`src/writer.c`)
- Writes decimated chunks and anomaly event windows / index to the filesystem.

## Configuration

The datalogger is configured via `config/logger.yaml`. This file defines sampling rates, anomaly thresholds, and buffer sizes.

## Data Formats

- **Decimated Stream**: Continuous, low-resolution time-series data.
- **Event Data**: Discontinuous, high-resolution snapshots of detected anomalies.
- **Event Index**: A queryable record of all detected events, used by the web UI for visualization.

## Dependencies

- `libyaml`: For parsing configuration files.
- `pthreads`: For multi-threaded execution.
- `shm_layout.h`: The shared memory contract (must match PRU firmware).
