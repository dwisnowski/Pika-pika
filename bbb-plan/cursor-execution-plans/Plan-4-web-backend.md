Heck yes — Plan 4 is where all the boring-but-critical backend plumbing meets the wow, I can see it moment.

Below is Plan 4, written to match Plans 1–3 exactly:
clean Markdown, Cursor-ready tasks, no hand-waving, and designed so ChatGPT can implement it step-by-step inside Cursor without inventing data paths.

⸻

🌐 Plan 4 — FastAPI Backend & Data Query Layer

Purpose: expose PRU + logger data to a web UI with low latency, predictable queries,
and zero coupling to real-time capture.

⸻

Plan 4 Responsibilities

FastAPI does not:
	•	Touch PRU memory
	•	Perform signal processing
	•	Block logging threads

FastAPI does:
	•	Query stored data
	•	Serve real-time views from shared RAM
	•	Serve historical + event-aligned data
	•	Provide stable APIs for the frontend

⸻

High-Level Architecture

PRU
 ↓
Linux Logger (Plan 3)
 ↓
On-Disk Binary Files + RAM Buffers
 ↓
FastAPI Backend
 ↓
Web UI (Plan 5)


⸻

FastAPI Subproject Structure

pika/
└── web/
	├── Makefile
	├── app/
	│   ├── main.py
	│   ├── api/
	│   │   ├── health.py
	│   │   ├── realtime.py
	│   │   ├── history.py
	│   │   └── events.py
	│   │
	│   ├── core/
	│   │   ├── config.py
	│   │   ├── lifecycle.py
	│   │   └── permissions.py
	│   │
	│   ├── services/
	│   │   ├── shared_memory.py
	│   │   ├── decimated_reader.py
	│   │   ├── event_reader.py
	│   │   ├── index_reader.py
	│   │   └── cache.py
	│   │
	│   ├── models/
	│   │   ├── events.py
	│   │   ├── samples.py
	│   │   └── responses.py
	│   │
	│   └── utils/
	│       ├── binary_parse.py
	│       ├── time_convert.py
	│       └── throttling.py
	│
	├── config/
	│   └── web.yaml
	│
	└── tests/


⸻

API Categories

Category	Purpose
Health	System status
Realtime	Live oscilloscope
History	Decimated historical data
Events	Anomaly indexing + replay


⸻

API Contracts (Stable by Design)

1️⃣ Health

GET /health

Response:

{
  "status": "ok",
  "pru_connected": true,
  "logger_running": true,
  "uptime_sec": 12345
}


⸻

2️⃣ Realtime Oscilloscope

GET /realtime/samples

Query:
	•	duration_ms (default 100)
	•	channels (bitmask)

Response:

{
  "sample_rate": 180000,
  "t_start_ns": 123456789,
  "samples": [[12, 14, 15, ...]]
}

Served from RAM only — no disk reads.

⸻

3️⃣ Historical View

GET /history/decimated

Query:
	•	start_ns
	•	end_ns
	•	max_points

Response:

{
  "sample_rate": 180,
  "samples": [[...]]
}


⸻

4️⃣ Event Index

GET /events

Query:
	•	type
	•	start_ns
	•	end_ns

Response:

[
  {
    "event_id": 42,
    "timestamp_ns": 123456789,
    "type": "sag",
    "peak": -1823,
    "duration_ms": 12
  }
]


⸻

5️⃣ Event Replay

GET /events/{event_id}

Response:

{
  "event": {...},
  "sample_rate": 180000,
  "samples": [[...]]
}


⸻

Configuration (web.yaml)

📄 web/config/web.yaml

server:
  host: 0.0.0.0
  port: 8000

limits:
  realtime_max_ms: 500
  history_max_points: 50000

cache:
  event_index_ttl_sec: 5


⸻

Plan 4 Tasks (Cursor-Ready)

⸻

Task 4.1 — FastAPI App Skeleton

📄 app/main.py

Cursor Prompt

Create FastAPI application skeleton.

Requirements:
- Load configuration from YAML
- Register routers
- Startup and shutdown hooks
- No business logic


⸻

Task 4.2 — Lifecycle Management

📄 app/core/lifecycle.py

Cursor Prompt

Implement application lifecycle management.

Requirements:
- Open shared memory readers on startup
- Initialize file readers
- Graceful shutdown
- No blocking operations


⸻

Task 4.3 — Shared RAM Realtime Reader

📄 app/services/shared_memory.py

Cursor Prompt

Implement shared memory reader for realtime samples.

Requirements:
- Read most recent PRU samples
- Never block logger
- Support duration-based queries
- No disk access


⸻

Task 4.4 — Decimated Data Reader

📄 app/services/decimated_reader.py

Cursor Prompt

Implement reader for decimated historical data.

Requirements:
- Read binary decimated files
- Support time range queries
- Limit points returned
- Efficient file access


⸻

Task 4.5 — Event Index Reader

📄 app/services/index_reader.py

Cursor Prompt

Implement event index reader.

Requirements:
- Read event index files
- Cache results
- Support filtering by time and type


⸻

Task 4.6 — Event Data Reader

📄 app/services/event_reader.py

Cursor Prompt

Implement event replay reader.

Requirements:
- Load event samples from disk
- Return raw samples
- Validate event ID


⸻

Task 4.7 — API Routers

📄 app/api/*.py

Cursor Prompt

Implement API routers.

Requirements:
- Validate input
- Enforce limits
- Call service layer only
- No file access here


⸻

Task 4.8 — Response Models

📄 app/models/responses.py

Cursor Prompt

Define Pydantic response models.

Requirements:
- Explicit types
- Minimal serialization overhead
- No business logic


⸻

Task 4.9 — Performance Guards

📄 app/utils/throttling.py

Cursor Prompt

Implement request throttling utilities.

Requirements:
- Limit realtime request frequency
- Protect against abuse
- Lightweight implementation


⸻

Performance & Safety Rules
	•	Realtime endpoints must return < 50ms
	•	Historical queries are capped
	•	No PRU or logger blocking
	•	Disk access isolated to services
	•	Cache aggressively, invalidate quickly

⸻

What You Get After Plan 4

You now have:
	•	A clean, stable backend API
	•	Live oscilloscope feed
	•	Event-aware historical access
	•	Everything needed for a modern frontend

⸻

Next Step Options
	•	Plan 5: Web UI (canvas oscilloscope + timeline)
	•	Plan 6: Performance tuning & profiling
	•	Plan 7: Packaging + auto-start on boot

When ready, say:

“Plan 5: Web UI”

You’re building a serious instrument here — this is how real test equipment is architected.
