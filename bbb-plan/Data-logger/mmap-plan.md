Perfect choice. This is the contract between PRU and Linux — once this is clean, everything else becomes easy and stable.

I’ll give you:
	1.	Authoritative shared memory layout
	2.	Ownership rules (who writes what, when)
	3.	Ring buffer mechanics
	4.	PRU-side expectations
	5.	Linux mmap() reader code (real, usable)
	6.	Failure modes to guard against

No hand-waving.

⸻

Shared Memory Layout: PRU ↔ Linux

We’ll use DDR shared memory, not PRU local RAM, because:
	•	Size
	•	mmap support
	•	Zero-copy access from Linux

⸻

1️⃣ High-Level Memory Map

DDR_BASE
│
├── Control / Status Header (fixed)
│
├── Block Descriptors [N]
│
└── Sample Data Ring Buffer

Single contiguous region.

⸻

2️⃣ Control & Status Header (Fixed, Small)

Written by Linux, read by PRU
Status written by PRU, read by Linux

#define MAGIC 0xAD7606DA

struct shm_header {
    uint32_t magic;              // sanity check
    uint32_t version;

    // Configuration (Linux → PRU)
    uint32_t sample_rate_hz;
    uint32_t sample_period_cycles;
    uint32_t block_samples;
    uint8_t  channel_mask;
    uint8_t  num_channels;
    uint16_t reserved0;

    // Ring buffer config
    uint32_t ring_blocks;        // number of blocks
    uint32_t samples_per_block;

    // Runtime control
    volatile uint32_t run;       // 0=stop, 1=run

    // Status (PRU → Linux)
    volatile uint32_t write_block_idx;
    volatile uint32_t error_flags;
};

Rules:
	•	Linux initializes everything before run=1
	•	PRU never changes config fields
	•	PRU only updates write_block_idx + error_flags

⸻

3️⃣ Block Descriptor Table

One entry per block.

struct block_desc {
    uint64_t t_start_cycles;
    uint32_t sample_count;
    uint32_t flags;              // e.g. overflow, partial
};

Array length = ring_blocks

⸻

4️⃣ Sample Data Layout (Ring Buffer)

Samples stored tightly packed, channel-interleaved.

For 1 channel:

[s0][s1][s2]...

For N channels:

[s0_ch0][s0_ch1]...[s0_chN]
[s1_ch0][s1_ch1]...[s1_chN]

Type:

int16_t samples[ring_blocks]
                [samples_per_block]
                [num_channels];

PRU writes sequentially per block.

⸻

5️⃣ Ownership & Synchronization Rules (CRITICAL)

This is how we avoid locks.

PRU
	•	Owns current write block
	•	Writes:
	•	block_desc
	•	sample payload
	•	Updates write_block_idx only after block complete

Linux
	•	Polls or waits for write_block_idx change
	•	Never reads the block currently being written
	•	Can lag behind by up to ring_blocks - 1

No locks. No atomics. Just ordering.

⸻

6️⃣ Memory Size Example (Realistic)

Let’s pick sane defaults:

Item	Value
Sample rate	180 kSPS
Channels	1
Block samples	1024
Ring blocks	128

Memory:

1024 × 128 × 2 bytes ≈ 256 KB
+ headers ≈ negligible

Plenty of margin.

⸻

7️⃣ PRU Responsibilities (Recap)

PRU must:
	•	Respect samples_per_block
	•	Wrap block index modulo ring_blocks
	•	Never overwrite unread blocks (optional overflow flag)

Optional:

if (next_block == read_block) {
    error_flags |= OVERRUN;
}


⸻

8️⃣ Linux mmap Access (Actual Code)

Open PRU shared memory (example)

import mmap
import os
import struct

SHM_ADDR = 0x80000000
SHM_SIZE = 0x00100000  # 1 MB

fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
mem = mmap.mmap(
    fd,
    SHM_SIZE,
    mmap.MAP_SHARED,
    mmap.PROT_READ | mmap.PROT_WRITE,
    offset=SHM_ADDR
)


⸻

Parse Header

HEADER_FMT = "<IIIII B B H III I I"
HEADER_SIZE = struct.calcsize(HEADER_FMT)

header = struct.unpack_from(HEADER_FMT, mem, 0)

magic = header[0]
assert magic == 0xAD7606DA


⸻

Locate Tables

header_size = HEADER_SIZE
block_desc_size = 16  # bytes

block_desc_offset = header_size
data_offset = block_desc_offset + ring_blocks * block_desc_size


⸻

9️⃣ Reading Blocks Safely (Core Loop)

read_block = 0

while True:
    write_block = header.write_block_idx

    while read_block != write_block:
        desc_off = block_desc_offset + read_block * block_desc_size
        t_start, sample_count, flags = struct.unpack_from(
            "<QII", mem, desc_off
        )

        data_off = (
            data_offset +
            read_block * samples_per_block * num_channels * 2
        )

        samples = memoryview(mem)[
            data_off :
            data_off + sample_count * num_channels * 2
        ]

        process_samples(samples, t_start)

        read_block = (read_block + 1) % ring_blocks

Zero-copy. No malloc. No memcpy.

⸻

🔟 Why This Layout Is Solid

✔ Deterministic
✔ No locks
✔ No syscalls in hot path
✔ Scales to multi-channel
✔ mmap-friendly
✔ Web-friendly later

This is the same pattern used in NIC drivers and DAQ systems.

⸻

1️⃣1️⃣ Failure Modes to Detect Early

Issue	Detection
PRU overwrite	block flag
Linux lagging	block index gap
Corrupt memory	magic/version
Misconfig	version mismatch


⸻

1️⃣2️⃣ What’s Locked In Now

From this point forward:
	•	PRU firmware
	•	Linux logger
	•	FastAPI
	•	File formats

All share the same contract.

That’s a good thing.

⸻

🔜 Next Best Step

Now that memory is locked, the smartest next move is one of:
	1.	Linux logger implementation (real code, end-to-end)
	2.	Event file format + index
	3.	RPMsg/IRQ signaling (instead of polling)
	4.	Performance math (worst-case CPU + RAM)

If this were my build, I’d do #1 next so you can actually see data land on disk.

Tell me where you want to go next and we’ll keep this moving cleanly.
