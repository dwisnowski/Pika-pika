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
- Maps `/dev/mem` to access the PRU shared memory region.
- Monitors `write_block_idx` in the `shm_header` to detect new data blocks.
- Transfers raw samples to an internal lock-free ring buffer for processing.

### 2. Processing Thread
- **Decimator (`src/decimator.c`)**: Downsamples the high-speed stream (e.g., 180kHz -> 1kHz) for continuous monitoring without filling up the disk.
- **Anomaly Detector (`src/anomaly_detector.c`)**: Runs thresholding logic to detect power quality events (Sag, Swell, Spike, Dip).
- **Event Manager (`src/event_window.c`)**: Maintains a circular buffer to capture pre-event samples and continues capturing post-event samples for a full-resolution "snapshot" of the anomaly.

### 3. Writer Thread (`src/writer.c`)
- Manages the transfer of data from RAM to the filesystem.
- Uses efficient binary formats to minimize overhead.
- Periodically flushes to prevent data loss.

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
