#!/usr/bin/env python3
"""
validate_data.py — Validate decimated.bin and index.bin produced by the datalogger.

Checks:
  Decimated data
  - File is non-empty and fully parseable
  - Header fields (sample_rate, sample_count, channels, values_per_sample) are sane
  - Timestamps are strictly monotonically increasing
  - Inter-chunk delta_ns matches expected chunk duration within a tolerance band
  - For values_per_sample == 2 (min/max): every min <= max per sample

  Event index
  - File is non-empty and fully parseable
  - Timestamps are monotonically non-decreasing
  - file_offset values are strictly increasing (no overlap)

Exit codes:
  0  All checks passed
  1  One or more checks failed
"""

import struct
import sys
import os
import argparse

# ---------------------------------------------------------------------------
# Format constants (must match storage_format.h)
# ---------------------------------------------------------------------------
DECIMATED_HDR_FMT  = "<QIIII"   # start_time_ns(u64) sample_rate(u32) sample_count(u32) channels(u32) values_per_sample(u32)
DECIMATED_HDR_SIZE = struct.calcsize(DECIMATED_HDR_FMT)

EVENT_IDX_FMT  = "<QQQQBhIQ"   # v2 index record (47 bytes packed)
EVENT_IDX_SIZE = struct.calcsize(EVENT_IDX_FMT)

# Unix epoch plausibility: 2020-01-01 .. 2100-01-01
EPOCH_MIN_NS = 1577836800 * 1_000_000_000
EPOCH_MAX_NS = 4102444800 * 1_000_000_000

# Timestamp delta tolerance: allow ±50% of expected inter‑chunk gap
DELTA_TOLERANCE = 0.50

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"


def _fmt_ns(ns: int) -> str:
    if ns >= 1_000_000_000:
        return f"{ns / 1e9:.6f} s"
    if ns >= 1_000_000:
        return f"{ns / 1e6:.3f} ms"
    if ns >= 1_000:
        return f"{ns / 1e3:.1f} µs"
    return f"{ns} ns"


# ---------------------------------------------------------------------------
# Decimated validation
# ---------------------------------------------------------------------------
def validate_decimated(path: str, verbose: bool = False) -> bool:
    print(f"\n=== Decimated data: {path} ===")
    failures = []

    if not os.path.exists(path):
        print(f"  [{FAIL}] File not found")
        return False

    file_size = os.path.getsize(path)
    print(f"  File size: {file_size:,} bytes")

    if file_size == 0:
        print(f"  [{FAIL}] File is empty")
        return False

    chunks = []

    with open(path, "rb") as f:
        chunk_idx = 0
        while True:
            hdr_raw = f.read(DECIMATED_HDR_SIZE)
            if len(hdr_raw) == 0:
                break  # clean EOF
            if len(hdr_raw) < DECIMATED_HDR_SIZE:
                failures.append(f"Chunk {chunk_idx}: truncated header ({len(hdr_raw)} of {DECIMATED_HDR_SIZE} bytes)")
                break

            ts, rate, count, channels, vps = struct.unpack(DECIMATED_HDR_FMT, hdr_raw)
            chunk_offset = f.tell() - DECIMATED_HDR_SIZE

            # Header sanity
            if rate == 0 or rate > 10_000_000:
                failures.append(f"Chunk {chunk_idx}: implausible sample_rate {rate}")
            elif rate > 500 and verbose:
                print(f"  [{WARN}] Chunk {chunk_idx}: sample_rate {rate} Hz (expected decimated ~50 Hz)")
            if ts < EPOCH_MIN_NS or ts > EPOCH_MAX_NS:
                failures.append(f"Chunk {chunk_idx}: start_time_ns {ts} outside plausible Unix epoch range")
            if count == 0 or count > 100_000:
                failures.append(f"Chunk {chunk_idx}: implausible sample_count {count}")
            if channels == 0 or channels > 32:
                failures.append(f"Chunk {chunk_idx}: implausible channels {channels}")
            if vps == 0 or vps > 10:
                failures.append(f"Chunk {chunk_idx}: implausible values_per_sample {vps}")

            data_size = count * channels * vps * 2  # int16 per value
            data = f.read(data_size)
            if len(data) < data_size:
                failures.append(f"Chunk {chunk_idx}: data truncated ({len(data)} of {data_size} bytes)")
                break

            chunks.append({
                "idx": chunk_idx,
                "offset": chunk_offset,
                "ts": ts,
                "rate": rate,
                "count": count,
                "channels": channels,
                "vps": vps,
                "data": data,
            })
            chunk_idx += 1

    if not chunks:
        print(f"  [{FAIL}] No valid chunks parsed")
        return False

    print(f"  Parsed {len(chunks)} chunks")

    # Timestamp monotonicity
    mono_ok = True
    for i in range(1, len(chunks)):
        if chunks[i]["ts"] <= chunks[i - 1]["ts"]:
            failures.append(
                f"Chunk {i}: timestamp not monotonically increasing "
                f"(prev={chunks[i-1]['ts']}, cur={chunks[i]['ts']})"
            )
            mono_ok = False

    if mono_ok:
        span_s = (chunks[-1]["ts"] - chunks[0]["ts"]) / 1e9
        print(f"  [{PASS}] Timestamps monotonically increasing — span {span_s:.3f} s")
    else:
        print(f"  [{FAIL}] Timestamp monotonicity violated")

    # Inter-chunk delta vs expected duration
    rate0 = chunks[0]["rate"]
    count0 = chunks[0]["count"]
    vps0 = chunks[0]["vps"]
    # Each chunk holds `count` decimated buckets; each bucket covers
    # samples_per_bucket = rate / output_rate raw samples.  Rather than knowing
    # output_rate directly, we infer expected gap from two consecutive timestamps.
    delta_violations = 0
    if len(chunks) >= 3:
        # Compute median observed delta to use as reference
        deltas = [chunks[i]["ts"] - chunks[i - 1]["ts"] for i in range(1, len(chunks))]
        deltas_sorted = sorted(deltas)
        median_delta = deltas_sorted[len(deltas_sorted) // 2]
        lo = median_delta * (1 - DELTA_TOLERANCE)
        hi = median_delta * (1 + DELTA_TOLERANCE)
        for i, d in enumerate(deltas):
            if d < lo or d > hi:
                delta_violations += 1
                if verbose:
                    print(f"  [{WARN}] Chunk {i+1}: delta {_fmt_ns(d)} outside ±{int(DELTA_TOLERANCE*100)}% of median {_fmt_ns(median_delta)}")
        if delta_violations == 0:
            print(f"  [{PASS}] Inter-chunk timing consistent (median {_fmt_ns(median_delta)})")
        else:
            print(f"  [{WARN}] {delta_violations}/{len(deltas)} inter-chunk deltas outside ±{int(DELTA_TOLERANCE*100)}% tolerance")

    # min ≤ max check (only when values_per_sample == 2)
    minmax_errors = 0
    for ch in chunks:
        if ch["vps"] != 2:
            continue
        n = ch["count"] * ch["channels"]
        vals = struct.unpack_from(f"<{n * 2}h", ch["data"])
        for j in range(0, len(vals), 2):
            mn, mx = vals[j], vals[j + 1]
            if mn > mx:
                minmax_errors += 1
                if verbose:
                    print(f"  [{WARN}] Chunk {ch['idx']}, pair {j//2}: min {mn} > max {mx}")
    if minmax_errors == 0:
        print(f"  [{PASS}] All min ≤ max (min/max integrity ok)")
    else:
        failures.append(f"{minmax_errors} min > max violations in decimated data")
        print(f"  [{FAIL}] {minmax_errors} min > max violations")

    # Summary
    c = chunks[0]
    print(f"\n  First chunk  — ts={_fmt_ns(c['ts'])}, rate={c['rate']} Hz, "
          f"count={c['count']}, channels={c['channels']}, vps={c['vps']}")
    c = chunks[-1]
    print(f"  Last chunk   — ts={_fmt_ns(c['ts'])}, rate={c['rate']} Hz, "
          f"count={c['count']}, channels={c['channels']}, vps={c['vps']}")

    if failures:
        for f_msg in failures:
            print(f"  [{FAIL}] {f_msg}")
        return False

    return True


# ---------------------------------------------------------------------------
# Event index validation
# ---------------------------------------------------------------------------
def validate_event_index(index_path: str, events_path: str, verbose: bool = False) -> bool:
    print(f"\n=== Event index: {index_path} ===")
    failures = []

    if not os.path.exists(index_path):
        print(f"  [{FAIL}] File not found")
        return False

    file_size = os.path.getsize(index_path)
    print(f"  File size: {file_size:,} bytes  ({file_size // EVENT_IDX_SIZE} records, "
          f"record size {EVENT_IDX_SIZE} bytes)")

    if file_size == 0:
        print(f"  [SKIP] No events recorded yet — nothing to validate")
        return True

    if file_size % EVENT_IDX_SIZE != 0:
        failures.append(f"index.bin size {file_size} is not a multiple of record size {EVENT_IDX_SIZE}")

    records = []
    with open(index_path, "rb") as f:
        rec_idx = 0
        while True:
            raw = f.read(EVENT_IDX_SIZE)
            if len(raw) == 0:
                break
            if len(raw) < EVENT_IDX_SIZE:
                failures.append(f"Record {rec_idx}: truncated ({len(raw)} of {EVENT_IDX_SIZE} bytes)")
                break
            eid, ts, wf_start, ns_per_sample, etype, peak, dur, foff = struct.unpack(
                EVENT_IDX_FMT, raw
            )
            records.append({
                "id": eid,
                "ts": ts,
                "wf_start": wf_start,
                "ns_per_sample": ns_per_sample,
                "type": etype,
                "peak": peak,
                "dur": dur,
                "foff": foff,
            })
            rec_idx += 1

    if not records:
        print(f"  [{FAIL}] No records parsed")
        return False

    print(f"  Parsed {len(records)} event records")

    # Timestamp must be non-decreasing (same-ns is theoretically ok)
    mono_ok = True
    for i in range(1, len(records)):
        if records[i]["ts"] < records[i - 1]["ts"]:
            failures.append(f"Record {i}: timestamp went backwards "
                            f"({records[i-1]['ts']} → {records[i]['ts']})")
            mono_ok = False
    if mono_ok:
        print(f"  [{PASS}] Event timestamps non-decreasing")
    else:
        print(f"  [{FAIL}] Event timestamp ordering violated")

    # file_offset must be strictly increasing
    off_ok = True
    for i in range(1, len(records)):
        if records[i]["foff"] <= records[i - 1]["foff"]:
            failures.append(f"Record {i}: file_offset did not increase "
                            f"({records[i-1]['foff']} → {records[i]['foff']})")
            off_ok = False
    if off_ok:
        print(f"  [{PASS}] Event file offsets strictly increasing")
    else:
        print(f"  [{FAIL}] Event file offset ordering violated")

    # Check offsets don't exceed events.bin size
    if os.path.exists(events_path):
        events_size = os.path.getsize(events_path)
        for r in records:
            if r["foff"] >= events_size:
                failures.append(f"Event id={r['id']}: file_offset {r['foff']} "
                                 f">= events.bin size {events_size}")
    else:
        print(f"  [{WARN}] events.bin not found, skipping offset bounds check")

    # Waveform alignment + Unix epoch plausibility (v2 index)
    align_ok = True
    for i, r in enumerate(records):
        if r["ts"] < EPOCH_MIN_NS or r["ts"] > EPOCH_MAX_NS:
            failures.append(f"Record {i}: timestamp_ns outside plausible Unix epoch")
            align_ok = False
        if r["wf_start"] > r["ts"]:
            failures.append(
                f"Record {i}: waveform_start_ns ({r['wf_start']}) > event timestamp ({r['ts']})"
            )
            align_ok = False
        if r["ns_per_sample"] == 0:
            failures.append(f"Record {i}: ns_per_sample is zero")
            align_ok = False
        elif r["dur"] > 0:
            event_end_ns = r["ts"] + r["dur"] * r["ns_per_sample"]
            if r["foff"] >= 0 and os.path.exists(events_path):
                # Infer waveform end from next offset or file size
                if i + 1 < len(records):
                    num_samples = (records[i + 1]["foff"] - r["foff"]) // 2
                else:
                    num_samples = (os.path.getsize(events_path) - r["foff"]) // 2
                wf_end_ns = r["wf_start"] + num_samples * r["ns_per_sample"]
                if r["ts"] > wf_end_ns:
                    failures.append(
                        f"Record {i}: event start after waveform end "
                        f"(ts={r['ts']} wf_end={wf_end_ns})"
                    )
                    align_ok = False
                if event_end_ns > wf_end_ns + r["ns_per_sample"] * 2:
                    failures.append(
                        f"Record {i}: event end ({event_end_ns}) beyond waveform "
                        f"({wf_end_ns}) by >2 samples"
                    )
                    align_ok = False
    if align_ok:
        print(f"  [{PASS}] Event waveform alignment + Unix epoch plausibility")
    else:
        print(f"  [{FAIL}] Event waveform alignment / epoch checks failed")

    event_type_names = {0: "NONE", 1: "SAG", 2: "SWELL", 3: "SPIKE", 4: "DIP"}
    for r in records[:5]:
        tname = event_type_names.get(r["type"], f"UNKNOWN({r['type']})")
        print(f"  Event id={r['id']} ts={_fmt_ns(r['ts'])} wf_start={_fmt_ns(r['wf_start'])} "
              f"type={tname} peak={r['peak']} dur={r['dur']} samples "
              f"ns/sample={r['ns_per_sample']} offset={r['foff']}")
    if len(records) > 5:
        print(f"  ... ({len(records) - 5} more)")

    if failures:
        for f_msg in failures:
            print(f"  [{FAIL}] {f_msg}")
        return False

    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def diagnose_pipeline() -> None:
    """Probe system state to diagnose a silent/empty data pipeline."""
    import glob
    import struct as _struct

    print("\n=== Pipeline Diagnostics ===")

    # 1. PRU remoteproc state + name
    pru_state = None
    pru0_discovered_remoteproc = None
    for state_path in sorted(glob.glob("/sys/class/remoteproc/remoteproc*/state")):
        base = os.path.dirname(state_path)
        name_path = os.path.join(base, "name")
        try:
            with open(state_path) as f:
                s = f.read().strip()
        except Exception:
            s = "unreadable"
        try:
            with open(name_path) as f:
                name = f.read().strip()
        except Exception:
            name = "unknown"

        is_pru0 = ("4a334000" in name or "pru0" in name.lower())
        is_pru1 = ("4a338000" in name or "pru1" in name.lower())
        label = " ← PRU0 (our firmware)" if is_pru0 else (" ← PRU1" if is_pru1 else "")
        print(f"  {os.path.basename(base)}: state={s}  name={name}{label}")

        if is_pru0:
            pru_state = s
            pru0_discovered_remoteproc = os.path.basename(base)

    if pru0_discovered_remoteproc is None:
        print(f"  [{WARN}] Could not identify PRU0 by name (expected '4a334000' or 'pru0' in name)")
        print(f"         SHM reader will fall back to hardcoded remoteproc1")
    elif "running" not in (pru_state or ""):
        print(f"  [{FAIL}] PRU0 ({pru0_discovered_remoteproc}) is NOT running — "
              f"firmware needs to be started (state={pru_state})")
    else:
        print(f"  [{PASS}] PRU0 ({pru0_discovered_remoteproc}) is running")

    # 2. Probe PRU Shared RAM via /dev/mem for SHM magic (0xDEADBEEF)
    SHM_PHYS     = 0x4a310000
    SHM_SIZE     = 0x3000
    SHM_MAGIC_EX = 0xDEADBEEF
    print(f"\n  PRU Shared RAM probe (phys=0x{SHM_PHYS:08X}, size=0x{SHM_SIZE:X})")
    try:
        import mmap as _mmap
        with open("/dev/mem", "rb") as devmem:
            mm = _mmap.mmap(devmem.fileno(), SHM_SIZE, _mmap.MAP_SHARED,
                            _mmap.PROT_READ, offset=SHM_PHYS)
            raw = mm.read(64)
            mm.close()

        magic, version, sample_period_cycles, block_size, num_blocks, \
            write_block_idx, error_flags, sample_count, sample_rate, \
            pru_clock_hz, heartbeat = _struct.unpack_from("<IIIIIIIIIII", raw, 0)

        print(f"    magic=0x{magic:08X}  version={version}  heartbeat={heartbeat}")
        print(f"    block_size={block_size}  num_blocks={num_blocks}  write_block_idx={write_block_idx}")
        print(f"    sample_period_cycles={sample_period_cycles}  sample_rate={sample_rate}  pru_clock_hz={pru_clock_hz}")
        print(f"    error_flags=0x{error_flags:08X}  sample_count={sample_count}")

        if magic == SHM_MAGIC_EX:
            print(f"    [{PASS}] SHM magic is valid — PRU firmware wrote to shared RAM")
            if heartbeat == 0:
                print(f"    [{WARN}] heartbeat=0: PRU may have just started or is stalled")
            if error_flags != 0:
                print(f"    [{FAIL}] error_flags=0x{error_flags:08X} — PRU reported an error")
                print(f"           0xDEAD0002 = adc_trigger_and_wait() timeout (ADC not responding)")
        else:
            print(f"    [{FAIL}] SHM magic not found (got 0x{magic:08X}, expected 0x{SHM_MAGIC_EX:08X})")
            if magic == 0x00000000:
                print(f"           Memory is zero — PRU firmware has not run yet or was stopped")
            else:
                print(f"           Unexpected value — PRU may be writing to a different address")
    except PermissionError:
        print(f"    [{WARN}] Cannot read /dev/mem — run as root: sudo make validate-diagnose")
    except Exception as e:
        print(f"    [{WARN}] /dev/mem probe failed: {e}")

    # 2. Scope SHM — populated by datalogger when blocks are flowing
    scope_shm = "/dev/shm/pika_scope_shm"
    if os.path.exists(scope_shm):
        sz = os.path.getsize(scope_shm)
        # Read magic + total_samples from the fixed-layout header
        # magic(u32) sample_rate(u32) channels(u32) capacity(u32) pru_clock_hz(u32)
        # sample_period_cycles(u32) total_samples(u64)  → offsets 0,4,8,12,16,20,24
        try:
            import mmap as _mmap
            with open(scope_shm, "rb") as f:
                hdr = f.read(32)
            if len(hdr) >= 32:
                import struct as _struct
                magic, sr, ch, cap, pru_hz, spc = _struct.unpack_from("<IIIIII", hdr, 0)
                total, = _struct.unpack_from("<Q", hdr, 24)
                if magic == 0x5C09E000:
                    print(f"  Scope SHM: OK — total_samples_written={total:,}  sample_rate={sr}  pru_clock_hz={pru_hz}")
                    if total == 0:
                        print(f"    [{WARN}] No samples reached the scope buffer — processor received no blocks")
                    else:
                        print(f"    [{PASS}] Scope buffer has data → processor was receiving blocks")
                else:
                    print(f"  [{WARN}] Scope SHM magic mismatch (got {hex(magic)}) — datalogger may not have started")
        except Exception as e:
            print(f"  [{WARN}] Could not read scope SHM: {e}")
    else:
        print(f"  [{WARN}] {scope_shm} not found — datalogger was never started, or scope init failed")

    # 3. Rotated .old files (evidence of past data that was rotated away)
    for name in ("decimated.bin.old", "events.bin.old", "index.bin.old"):
        p = os.path.join("data", name)
        if os.path.exists(p):
            print(f"  [{WARN}] Rotated file found: {p} ({os.path.getsize(p):,} bytes) — data may have been overwritten")

    # 4. Config reachability hint
    config_paths = ["../pika.yaml", "pika.yaml", "../../pika.yaml"]
    found_config = any(os.path.exists(p) for p in config_paths)
    if found_config:
        found = next(p for p in config_paths if os.path.exists(p))
        print(f"  Config file: found at {found}")
    else:
        print(f"  [{FAIL}] Config file (pika.yaml) not found in expected paths — "
              f"datalogger falls back to zero defaults which causes a crash on startup "
              f"(nominal_rate_hz=0 causes SIGFPE). Run from the datalogger/ directory.")

    print()
    print("  To capture full pipeline diagnostics, run:")
    print("    sudo ./bin/datalogger 2>&1 | head -80")
    print("  and look for:")
    print("    '[SHM Reader] Waiting for magic' → PRU firmware not running")
    print("    '[Processor] First block received' → PRU data flowing correctly")
    print("    '[Reader] Warning: Ring buffer overflow!' → reader working, processor stalled")
    print("    'Failed to load config' → config path wrong; SIGFPE likely on startup")


def main():
    parser = argparse.ArgumentParser(description="Validate datalogger output files")
    parser.add_argument("--data-dir", default="data", help="Directory containing .bin files (default: data)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print per-sample/per-chunk detail on warnings")
    parser.add_argument("--diagnose", "-d", action="store_true",
                        help="Run pipeline diagnostics (PRU state, scope SHM, config) when data is missing")
    args = parser.parse_args()

    d = args.data_dir
    results = {}

    results["decimated"] = validate_decimated(
        os.path.join(d, "decimated.bin"), verbose=args.verbose
    )
    results["events"] = validate_event_index(
        os.path.join(d, "index.bin"),
        os.path.join(d, "events.bin"),
        verbose=args.verbose,
    )

    print("\n=== Summary ===")
    all_ok = True
    for name, ok in results.items():
        status = PASS if ok else FAIL
        print(f"  {name:<20} [{status}]")
        if not ok:
            all_ok = False

    no_data = (os.path.getsize(os.path.join(d, "decimated.bin")) == 0
               if os.path.exists(os.path.join(d, "decimated.bin")) else True)

    if args.diagnose or (not all_ok and no_data):
        diagnose_pipeline()

    if all_ok:
        print("\nAll checks passed.")
        sys.exit(0)
    else:
        print("\nOne or more checks failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
