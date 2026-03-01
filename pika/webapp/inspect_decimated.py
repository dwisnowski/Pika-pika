#!/usr/bin/env python3
"""
Inspect decimated.bin file structure and contents.
Helps debug data format issues between datalogger and webapp.
"""

import struct
import sys
import os

# Header format: uint64 + 4x uint32
HEADER_FORMAT_NEW = "<QIIII"  # 24 bytes: start_time_ns, sample_rate, sample_count, channels, values_per_sample
HEADER_FORMAT_OLD = "<QIII"   # 20 bytes: start_time_ns, sample_rate, sample_count, channels
HEADER_SIZE_NEW = struct.calcsize(HEADER_FORMAT_NEW)
HEADER_SIZE_OLD = struct.calcsize(HEADER_FORMAT_OLD)

def inspect_file(filepath, max_chunks=10):
    """Inspect decimated.bin file structure."""
    
    if not os.path.exists(filepath):
        print(f"ERROR: File not found: {filepath}")
        return False
    
    file_size = os.path.getsize(filepath)
    print(f"File: {filepath}")
    print(f"Size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
    print()
    
    if file_size == 0:
        print("File is empty!")
        return False
    
    with open(filepath, "rb") as f:
        # Try to read first chunk to detect format
        f.seek(0)
        hdr_data = f.read(HEADER_SIZE_NEW)
        
        if len(hdr_data) < HEADER_SIZE_NEW:
            print(f"ERROR: File too small to read header (got {len(hdr_data)} bytes, need {HEADER_SIZE_NEW})")
            return False
        
        # Try new format first
        try:
            ts, rate, count, channels, values_per_sample = struct.unpack(HEADER_FORMAT_NEW, hdr_data)
            header_format = "NEW (24 bytes)"
            header_size = HEADER_SIZE_NEW
        except:
            # Try old format
            try:
                ts, rate, count, channels = struct.unpack(HEADER_FORMAT_OLD, hdr_data[:HEADER_SIZE_OLD])
                values_per_sample = 0  # Not present in old format
                header_format = "OLD (20 bytes)"
                header_size = HEADER_SIZE_OLD
            except:
                print("ERROR: Could not parse header in either format")
                print(f"Raw header bytes: {hdr_data.hex()}")
                return False
        
        print(f"Header Format: {header_format}")
        print(f"First Chunk Header:")
        print(f"  start_time_ns: {ts}")
        print(f"  sample_rate: {rate} Hz")
        print(f"  sample_count: {count}")
        print(f"  channels: {channels}")
        if header_format == "NEW (24 bytes)":
            print(f"  values_per_sample: {values_per_sample}")
        print()
        
        # Sanity check
        if count == 0 or count > 100000:
            print(f"WARNING: sample_count looks suspicious: {count}")
        if channels == 0 or channels > 32:
            print(f"WARNING: channels looks suspicious: {channels}")
        if header_format == "NEW (24 bytes)" and (values_per_sample == 0 or values_per_sample > 10):
            print(f"WARNING: values_per_sample looks suspicious: {values_per_sample}")
        
        # Calculate expected data size
        if header_format == "NEW (24 bytes)":
            expected_data_size = count * channels * values_per_sample * 2
        else:
            expected_data_size = count * channels * 2
        
        print(f"Expected data size for first chunk: {expected_data_size} bytes")
        print()
        
        # Read and display chunks
        f.seek(0)
        chunk_num = 0
        total_samples = 0
        
        while chunk_num < max_chunks:
            hdr_data = f.read(header_size)
            if len(hdr_data) < header_size:
                print(f"Reached end of file at chunk {chunk_num}")
                break
            
            if header_format == "NEW (24 bytes)":
                ts, rate, count, channels, values_per_sample = struct.unpack(HEADER_FORMAT_NEW, hdr_data)
                data_size = count * channels * values_per_sample * 2
            else:
                ts, rate, count, channels = struct.unpack(HEADER_FORMAT_OLD, hdr_data)
                data_size = count * channels * 2
            
            print(f"Chunk {chunk_num}:")
            print(f"  Offset: {f.tell() - header_size} bytes")
            print(f"  sample_rate: {rate} Hz, count: {count}, channels: {channels}", end="")
            if header_format == "NEW (24 bytes)":
                print(f", values_per_sample: {values_per_sample}")
            else:
                print()
            print(f"  Data size: {data_size} bytes")
            
            # Sanity check data size
            if data_size > 10000000:  # 10MB seems unreasonable for a single chunk
                print(f"  ERROR: Data size is unreasonably large ({data_size} bytes)")
                print(f"  This suggests the header is corrupt or misaligned")
                break
            
            # Read data
            data = f.read(data_size)
            if len(data) < data_size:
                print(f"  ERROR: Incomplete data (got {len(data)} bytes, expected {data_size})")
                break
            
            # Parse and display first few values
            if len(data) > 0:
                num_values = min(10, len(data) // 2)
                shorts = struct.unpack(f"<{num_values}h", data[:num_values * 2])
                print(f"  First {num_values} values: {shorts}")
            
            total_samples += count
            chunk_num += 1
            print()
        
        print(f"Summary:")
        print(f"  Chunks read: {chunk_num}")
        print(f"  Total samples: {total_samples}")
        print(f"  File position: {f.tell()} bytes")
        
        return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        # Default path
        filepath = "pika/datalogger/data/decimated.bin"
    
    max_chunks = 10
    if len(sys.argv) > 2:
        max_chunks = int(sys.argv[2])
    
    success = inspect_file(filepath, max_chunks)
    sys.exit(0 if success else 1)
