Perfect — this is the Linux-side brain of your system. What you’re describing is essentially a streaming DAQ recorder with trigger-based high-resolution retention, very similar to how power quality analyzers and event recorders work.

I’ll break this into clear, buildable layers, then give you a concrete data model + code skeleton that can actually be implemented without repainting walls later.

⸻

Linux Logger + Anomaly Engine (Design & Skeleton)

Big Picture Data Flow

PRU → Shared DDR Ring Buffer
        ↓
Linux Reader (zero-copy / mmap)
        ↓
Streaming Anomaly Detector
        ↓
┌───────────────┬────────────────────┐
│ High-Res RAM  │ Decimated RAM       │
│ (events only) │ (continuous trend)  │
└───────────────┴────────────────────┘
        ↓ (buffer full)
     Disk write (batch)

Key principles:
	•	Never block PRU
	•	Single pass over data
	•	RAM first, disk second
	•	Binary formats, not CSV

⸻

1️⃣ Memory Interface (PRU → Linux)

Access method
	•	Linux mmap() the DDR region used by PRU
	•	PRU writes fixed-size blocks
	•	Linux polls or waits via RPMsg/IRQ

Linux-side assumptions
	•	Blocks arrive sequentially
	•	Each block contains:
	•	block timestamp
	•	N samples
	•	1–8 channels (start with 1)

No copying until necessary.

⸻

2️⃣ Sample Representation (Linux)

Internally (RAM):

# 16-bit signed ADC values
int16 samples

# Converted only when needed
float32 volts

⚠ Keep raw ADC counts as long as possible
⚠ Convert to volts only for anomaly logic + metadata

⸻

3️⃣ Timebase Model (Important)

PRU provides:
	•	t_start_cycles

Linux converts:

timestamp = base_time + (cycles / 200e6)

This gives:
	•	Sub-µs relative accuracy
	•	Wall-clock alignment later

⸻

4️⃣ Anomaly Definitions (Simple, Extensible)

Start simple and robust.

Event	Detection
Spike	
Sag	RMS below low threshold for N samples
Swell	RMS above high threshold for N samples
Dip	Short-duration sag

All thresholds configurable.

⸻

5️⃣ Pre/Post Capture Logic

Fixed window
	•	0.5 s before
	•	0.5 s after

At 180 kSPS:

0.5 s → 90,000 samples

Strategy
	•	Maintain circular pre-trigger buffer
	•	On anomaly:
	•	Freeze pre-buffer
	•	Start post-buffer countdown
	•	Promote samples to high-res event record

This avoids retroactive disk reads.

⸻

6️⃣ Decimation Strategy (Continuous Data)

Default

decimation = 1000

Meaning:
	•	Keep 1 sample per 1000
	•	~180 SPS stored continuously

Configurable
	•	Range: 2 → 10,000
	•	Applied only outside anomaly windows

Method

Efficient and deterministic:

if sample_index % decimation == 0:
    store_decimated(sample)

No averaging initially (can add later).

⸻

7️⃣ Storage Model (Efficient + Future-Proof)

7.1 High-Resolution Event Records (Binary)

Each event stored as one file or one block.

Header (fixed-size):

struct event_header {
    uint64_t timestamp_ns;
    float    event_voltage;
    uint32_t event_type;
    uint32_t sample_rate;
    uint32_t pre_samples;
    uint32_t post_samples;
};

Payload:

int16 raw_samples[pre + post]

✔ Small
✔ Fast
✔ Lossless
✔ Easy to plot later

⸻

7.2 Continuous Decimated Data

Use chunked binary append:

struct decimated_record {
    uint64_t timestamp_ns;
    int16    sample;
};

Stored in:
	•	Rolling file per hour/day
	•	Append-only

Later:
	•	Memory-map for plotting
	•	Overlay events by timestamp

⸻

8️⃣ RAM Buffering Strategy (Disk Friendly)

RAM buffers
	•	decimated_buffer (e.g. 1–5 MB)
	•	event_buffer (per-event, flushed immediately after event)

Write policy
	•	Write only when:
	•	Buffer full
	•	Shutdown
	•	Event completed

No per-sample writes.

⸻

9️⃣ Linux Process Architecture

Single process is fine at first.

Threads:
	1.	PRU reader
	2.	Anomaly detector + router
	3.	Disk writer

Queues between them (lock-free or queue.Queue).

⸻

🔟 Python Skeleton (Realistic, Not Toy)

This is intentionally clean and expandable.

class CircularBuffer:
    def __init__(self, size):
        self.buf = np.zeros(size, dtype=np.int16)
        self.idx = 0

    def push(self, sample):
        self.buf[self.idx] = sample
        self.idx = (self.idx + 1) % len(self.buf)

    def snapshot(self):
        return np.roll(self.buf, -self.idx).copy()


⸻

Anomaly Detector Core

class AnomalyDetector:
    def __init__(self, cfg):
        self.pre_buffer = CircularBuffer(cfg.pre_samples)
        self.post_remaining = 0
        self.current_event = None

    def process(self, sample, timestamp):
        self.pre_buffer.push(sample)

        if self.detect(sample):
            self.start_event(sample, timestamp)

        if self.current_event:
            self.current_event.append(sample)
            self.post_remaining -= 1
            if self.post_remaining == 0:
                self.finish_event()

    def detect(self, sample):
        return abs(sample) > self.cfg.spike_threshold


⸻

1️⃣1️⃣ Why This Design Works Well Later

✔ FastAPI can:
	•	Load decimated file
	•	Overlay event timestamps
	•	Load event payload on demand

✔ PRU untouched
✔ Storage scales
✔ Disk wear minimized
✔ Analysis decoupled from capture

⸻

1️⃣2️⃣ What We Did Not Do (Yet)

Intentionally deferred:
	•	RMS windows
	•	Averaging decimation
	•	Multi-channel correlation
	•	Compression (can be added later)

You now have a clean core.

⸻

🔜 Next Best Step

The next thing to lock in is one of these:
	1.	Exact shared-memory layout + mmap code
	2.	Binary file format spec (event + decimated)
	3.	Anomaly thresholds & power-quality definitions
	4.	FastAPI data access patterns
	5.	Performance math (CPU & RAM usage)

If this were my project, I’d do #1 next, because it locks Linux ↔ PRU forever.

Tell me what you want to tackle next and we’ll keep this tight and professional.
