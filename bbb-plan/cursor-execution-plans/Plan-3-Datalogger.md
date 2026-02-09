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
    │   ├── shm_layout.h        # MUST match PRU project (single source of truth)
    │   │                       # Contains: shm_header, block_desc from mmap-plan.md
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

⚠️  CRITICAL: shm_layout.h must be kept in sync with PRU firmware.
    Consider symlinking or copying from pika/pru/include/shm_layout.h


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

Implementation Language & Dependencies

Language: C (for performance and zero-copy memory access)

Required Libraries:
- libyaml (for config parsing)
- pthread (for threading)
- Standard POSIX (mmap, clock_gettime)

Build System: GNU Make

⸻

Shared Memory Contract (Reference)

The PRU ↔ Linux interface is fully specified in:
📄 bbb-plan/Data-logger/mmap-plan.md

Key structures to implement in shm_layout.h:

struct shm_header {
    uint32_t magic;              // 0xAD7606DA
    uint32_t version;
    uint32_t sample_rate_hz;
    uint32_t sample_period_cycles;
    uint32_t block_samples;
    uint8_t  channel_mask;
    uint8_t  num_channels;
    uint16_t reserved0;
    uint32_t ring_blocks;
    uint32_t samples_per_block;
    volatile uint32_t run;
    volatile uint32_t write_block_idx;
    volatile uint32_t error_flags;
};

struct block_desc {
    uint64_t t_start_cycles;
    uint32_t sample_count;
    uint32_t flags;
};

Memory Layout:
[shm_header][block_desc array][sample ring buffer]

⸻

Plan 3 Tasks (Cursor-Ready)

⸻

Task 3.1 — Shared Memory Reader

📄 src/shm_reader.c

Cursor Prompt

Write code to read PRU shared DDR ring buffer.

Requirements:
- Map PRU shared memory via /dev/mem (see mmap-plan.md for exact layout)
- Use the exact structures from mmap-plan.md:
  * shm_header with MAGIC 0xAD7606DA
  * block_desc table
  * Ring buffer ownership rules
- Detect new blocks via write_block_idx polling
- Never overwrite unread data
- Implement zero-copy memoryview access pattern
- Expose blocks to the processing pipeline
- No signal processing here

Reference: bbb-plan/Data-logger/mmap-plan.md sections 2-9


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
- Load config from YAML (using libyaml)
- Validate shm_header.magic == 0xAD7606DA
- Validate shm_header.version compatibility
- Start worker threads (reader, processor, writer)
- Handle shutdown cleanly (SIGINT/SIGTERM)
- Validate PRU firmware compatibility via version field


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
	•	A production-grade C logger
	•	Indexed anomaly events
	•	Efficient historical storage
	•	Clean input for FastAPI visualization
	•	Zero-copy shared memory reader
	•	Lock-free ring buffer implementation

⸻

Testing Strategy

Unit Tests:
- Ring buffer wrapping
- Decimation accuracy
- Anomaly threshold detection
- Time conversion accuracy

Integration Tests:
- Mock PRU shared memory
- End-to-end data flow
- File format validation

Performance Tests:
- CPU usage at 180 kSPS
- Memory footprint
- Disk write batching efficiency

⸻

Reference Documents

This plan builds on:
- bbb-plan/Data-logger/High-level-plan.md (architecture)
- bbb-plan/Data-logger/mmap-plan.md (memory contract)
- pika/pru/include/shm_layout.h (shared structures)
