#!/usr/bin/env python
"""
Benchmark Python TDS serialization performance (without database).

Measures how fast Python can serialize data to TDS wire format.
"""

import time
from tds_serializer import TdsSerializer

NUM_ROWS = 500_000


def benchmark_python_serialization():
    """Benchmark Python-side TDS serialization speed."""
    
    # Define schema
    column_types = ['INT', 'NVARCHAR', 'BIT', 'FLOAT']
    serializer = TdsSerializer(column_types)
    
    # Generate test data
    print(f"Generating {NUM_ROWS:,} test rows...")
    rows_data = [
        [i, f"Name_{i}", i % 2 == 0, i * 1.5]
        for i in range(NUM_ROWS)
    ]
    print(f"Data size: {len(rows_data):,} rows")
    
    # Benchmark serialization
    print(f"\nBenchmarking TDS serialization...")
    start = time.perf_counter()
    
    serialized_rows = [serializer.serialize_row(row) for row in rows_data]
    
    elapsed = time.perf_counter() - start
    
    # Calculate metrics
    throughput = NUM_ROWS / elapsed
    time_per_row_us = (elapsed * 1_000_000) / NUM_ROWS
    total_bytes = sum(len(row_bytes) for row_bytes in serialized_rows)
    bytes_per_row = total_bytes / NUM_ROWS
    
    # Print results
    print(f"\nResults:")
    print(f"  Rows serialized: {NUM_ROWS:,}")
    print(f"  Time: {elapsed:.3f}s")
    print(f"  Throughput: {throughput:,.0f} rows/s")
    print(f"  Time per row: {time_per_row_us:.2f} µs")
    print(f"  Total bytes: {total_bytes:,}")
    print(f"  Bytes per row: {bytes_per_row:.1f}")
    print(f"  Bandwidth: {total_bytes / elapsed / 1_000_000:.1f} MB/s")
    
    # Sample serialized data
    print(f"\nSample serialized row (first 100 bytes):")
    print(f"  {serialized_rows[0][:100].hex()}")
    
    # Compare to target
    print(f"\nComparison to pure Rust (750k rows/s):")
    if throughput >= 750_000:
        print(f"  ✅ FASTER: {throughput / 750_000:.2f}x")
    else:
        print(f"  ⚠️  SLOWER: {throughput / 750_000:.2f}x")
    
    # Estimate overhead
    print(f"\nEstimated overhead breakdown:")
    print(f"  Python serialization: {time_per_row_us:.2f} µs/row ({time_per_row_us / (1_000_000 / throughput) * 100:.1f}%)")
    print(f"  Remaining (GIL + copy + TDS write): {1_000_000 / 750_000 - time_per_row_us:.2f} µs/row")
    
    return throughput


if __name__ == "__main__":
    benchmark_python_serialization()
