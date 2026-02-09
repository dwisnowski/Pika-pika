Perfect — this is where the project really starts to feel like a system instead of just firmware.

Below is Plan 3, written in the same Cursor-ready, copy/paste Markdown style as Plans 1 & 2.
It is structured so ChatGPT inside Cursor can implement it task-by-task without guessing.

⸻

📊 Plan 3 — Linux Datalogger & Anomaly Engine

Purpose: consume PRU data deterministically, detect power-quality anomalies,
store data efficiently, and prepare everything needed for historical visualization.

⸻

Plan 3: Linux Logger Architecture

Core Responsibilities
	•	Read continuous sample blocks from PRU shared memory
	•	Perform real-time anomaly detection
	•	Maintain pre-event and post-event high-resolution buffers
	•	Decimate non-event data aggressively
	•	Store data efficiently (RAM-first, disk-second)
	•	Produce a queryable event index for the web UI

⸻

High-Level Data Flow

PRU → Shared DDR Ring Buffer
        ↓
Linux Reader Thread
        ↓
Signal Processing Pipeline
  ├── Decimator
  ├── Anomaly Detector
  └── Event Window Extractor
        ↓
RAM Buffers
        ↓ (flush on threshold)
Efficient On-Disk Storage


⸻

Datalogger Subproject Structure

pika/
└── datalogger/
    ├── Makefile
    ├── src/
    │   ├── main.c
    │   ├── shm_reader.c
    │   ├── ring_buffer.c
    │   ├── decimator.c
    │   ├── anomaly_detector.c
    │   ├── event_window.c
    │   ├── writer.c
    │   ├── time_utils.c
    │   └── config.c
    │
    ├── include/
    │   ├── shm_layout.h        # Copied from PRU project (single source of truth)
    │   ├── logger_config.h
    │   ├── event_types.h
    │   └── storage_format.h
    │
    ├── config/
    │   └── logger.yaml
    │
    ├── data/
    │   ├── events/
    │   ├── decimated/
    │   └── index/
    │
    └── tests/


⸻

Configuration File (logger.yaml)

📄 datalogger/config/logger.yaml

sampling:
  nominal_rate_hz: 180000
  channels: 1

decimation:
  normal_rate: 1000          # default 1/1000
  min_rate: 2
  max_rate: 10000

anomalies:
  sag:
    threshold_pct: -10
    min_duration_ms: 8
  swell:
    threshold_pct: 10
    min_duration_ms: 8
  spike:
    threshold_pct: 30
    max_duration_ms: 2
  dip:
    threshold_pct: -30
    max_duration_ms: 2

event_window:
  pre_event_sec: 0.5
  post_event_sec: 0.5

buffers:
  ram_flush_mb: 64


⸻

Storage Strategy (Critical)

Event Data (High Precision)
	•	Full 16-bit samples
	•	No decimation
	•	Stored per-event
	•	Time-aligned
	•	Compact binary format

Non-Event Data
	•	Decimated stream only
	•	Configurable decimation factor
	•	Stored as time-series chunks

Index
	•	One record per anomaly
	•	Fast lookup for web UI

⸻

On-Disk Formats

Event Index Record

struct event_index_record {
    uint64_t event_id;
    uint64_t timestamp_ns;
    uint8_t  event_type;      // sag, swell, spike, dip
    int16_t  peak_value;
    uint32_t duration_samples;
    uint64_t file_offset;
};


⸻

Event Sample Storage

struct event_file_header {
    uint64_t event_id;
    uint64_t timestamp_ns;
    uint8_t  channel_mask;
    uint32_t sample_rate;
};

(samples follow, raw int16)

⸻

Decimated Data Chunk

struct decimated_chunk_header {
    uint64_t start_time_ns;
    uint32_t sample_rate;
    uint32_t sample_count;
};


⸻

Threads & Responsibilities

Thread	Role
Reader	Pull blocks from PRU shared memory
Processor	Detect anomalies & decimate
Event Manager	Manage pre/post buffers
Writer	Flush RAM buffers to disk

No thread is allowed to block PRU consumption

⸻

Plan 3 Tasks (Cursor-Ready)

⸻

Task 3.1 — Shared Memory Reader

📄 src/shm_reader.c

Cursor Prompt

Write code to read PRU shared DDR ring buffer.

Requirements:
- Map PRU shared memory via /dev/mem
- Detect new blocks via write_block_idx
- Never overwrite unread data
- Expose blocks to the processing pipeline
- No signal processing here


⸻

Task 3.2 — Ring Buffer Abstraction

📄 src/ring_buffer.c

Cursor Prompt

Implement a lock-free ring buffer for sample blocks.

Requirements:
- Single producer, single consumer
- Fixed-size blocks
- No malloc in hot path
- Explicit overflow detection


⸻

Task 3.3 — Decimator

📄 src/decimator.c

Cursor Prompt

Implement a configurable decimator.

Requirements:
- Support rates from 1/2 to 1/10000
- Deterministic sample selection (no averaging)
- Handle channel masks
- Bypass decimation for event windows


⸻

Task 3.4 — Anomaly Detector

📄 src/anomaly_detector.c

Cursor Prompt

Implement anomaly detection logic.

Detect:
- Sag
- Swell
- Spike
- Dip

Requirements:
- Operate on raw samples
- Threshold-based
- Track duration
- Emit event start/stop markers
- No dynamic memory


⸻

Task 3.5 — Event Window Manager

📄 src/event_window.c

Cursor Prompt

Implement pre/post event buffering.

Requirements:
- Circular pre-event buffer (0.5s)
- Capture post-event samples (0.5s)
- Support overlapping events
- Provide finalized event buffers to writer


⸻

Task 3.6 — RAM-First Writer

📄 src/writer.c

Cursor Prompt

Implement RAM-backed storage writer.

Requirements:
- Accumulate data in RAM
- Flush to disk on size threshold
- Separate files for:
  - Event data
  - Decimated data
  - Event index
- Binary formats only


⸻

Task 3.7 — Time Synchronization

📄 src/time_utils.c

Cursor Prompt

Implement time utilities.

Requirements:
- Convert PRU sample index to CLOCK_MONOTONIC time
- Handle drift estimation
- No system calls in hot path


⸻

Task 3.8 — Main Orchestrator

📄 src/main.c

Cursor Prompt

Implement datalogger main program.

Requirements:
- Load config from YAML
- Start worker threads
- Handle shutdown cleanly
- Validate PRU firmware compatibility


⸻

Validation Rules
	•	PRU reader must never block
	•	Anomaly detection must run faster than real time
	•	Disk writes are batch-only
	•	Event data must be lossless
	•	Decimated data may drop samples, never events

⸻

Deliverables After Plan 3

You will have:
	•	A production-grade logger
	•	Indexed anomaly events
	•	Efficient historical storage
	•	Clean input for FastAPI visualization
