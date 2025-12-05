#!/usr/bin/env python3
"""
Benchmark fast-path optimization with a wide table (1000 integer columns).
Tests type conversion overhead when dealing with many columns.
Runs the test 10 times and reports statistics.
"""

import os
os.environ['RUST_LOG'] = 'error'  # Disable tracing for accurate measurement

import mssql_python
import time
import statistics

# Connection details
SERVER = "localhost"
DATABASE = "master"
USER = "sa"
PASSWORD = open("/tmp/password").read().strip()
TABLE_NAME = "benchmark_wide_fastpath"
NUM_ROWS = 100_000  # Reduced since we have 1000 columns
NUM_COLUMNS = 1000
NUM_RUNS = 10


def run_single_test():
    """Run a single bulkcopy test and return throughput."""
    conn_str = f"Server={SERVER};Database={DATABASE};UID={USER};PWD={PASSWORD}"
    connection = mssql_python.connect(conn_str)
    cursor = connection.cursor()
    
    # Create table with 1000 INT columns
    cursor.execute(f"IF OBJECT_ID('{TABLE_NAME}', 'U') IS NOT NULL DROP TABLE {TABLE_NAME}")
    
    # Build CREATE TABLE statement with 1000 columns
    columns = ", ".join([f"col{i} INT" for i in range(NUM_COLUMNS)])
    cursor.execute(f"CREATE TABLE {TABLE_NAME} ({columns})")
    connection.commit()
    
    # Generate test data - tuples of 1000 integers
    rows_data = [
        tuple(i * 1000 + j for j in range(NUM_COLUMNS))
        for i in range(NUM_ROWS)
    ]
    
    # Import Core TDS module
    from mssql_core_tds import DdbcConnection as CoreDdbcConnection
    from mssql_python.client_context_builder import ClientContextBuilder
    
    # Get Core TDS connection string and create temporary connection
    connection_string = connection.get_core_connection_string()
    client_context = ClientContextBuilder.build_from_connection_string(connection_string)
    
    core_connection = None
    try:
        core_connection = CoreDdbcConnection(client_context)
        core_cursor = core_connection.cursor()
        
        # Column mappings for all 1000 columns
        column_mappings = [(i, f"col{i}") for i in range(NUM_COLUMNS)]
        
        # Bulk insert with fast-path optimization
        start = time.perf_counter()
        
        result = core_cursor.bulkcopy(
            TABLE_NAME,
            iter(rows_data),
            {"batch_size": 0, "timeout": 60, "column_mappings": column_mappings}
        )
        
        elapsed = time.perf_counter() - start
        
        throughput = NUM_ROWS / elapsed
        time_per_row = elapsed / NUM_ROWS * 1_000_000  # microseconds
        
        return {
            'throughput': throughput,
            'time_per_row': time_per_row,
            'total_time': elapsed,
            'rows_copied': result
        }
        
    finally:
        if core_connection:
            core_connection.close()
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
        connection.commit()
        connection.close()


def main():
    print("Fast-Path Wide Table (1000 INT columns) Benchmark")
    print("=" * 70)
    print(f"Configuration:")
    print(f"  Rows per test: {NUM_ROWS:,}")
    print(f"  Columns per row: {NUM_COLUMNS}")
    print(f"  Number of runs: {NUM_RUNS}")
    print(f"  Server: {SERVER}")
    print(f"  Database: {DATABASE}")
    print("=" * 70)
    print()
    
    results = []
    
    for i in range(NUM_RUNS):
        print(f"Run {i+1}/{NUM_RUNS}... ", end='', flush=True)
        try:
            result = run_single_test()
            results.append(result)
            print(f"{result['throughput']:,.0f} rows/s ({result['time_per_row']:.2f} µs/row, {result['total_time']:.3f}s total)")
        except Exception as e:
            print(f"FAILED: {e}")
    
    if not results:
        print("\n❌ All runs failed!")
        return
    
    # Calculate statistics
    throughputs = [r['throughput'] for r in results]
    times_per_row = [r['time_per_row'] for r in results]
    total_times = [r['total_time'] for r in results]
    
    print()
    print("=" * 70)
    print(f"RESULTS ({len(results)} successful runs):")
    print("=" * 70)
    print()
    print("Throughput (rows/s):")
    print(f"  Average:        {statistics.mean(throughputs):,.0f}")
    print(f"  Median:         {statistics.median(throughputs):,.0f}")
    print(f"  Min:            {min(throughputs):,.0f}")
    print(f"  Max:            {max(throughputs):,.0f}")
    if len(throughputs) > 1:
        print(f"  Std Dev:         {statistics.stdev(throughputs):,.0f}")
    print()
    print("Time per row (µs):")
    print(f"  Average:         {statistics.mean(times_per_row):.2f}")
    print(f"  Median:          {statistics.median(times_per_row):.2f}")
    print(f"  Min:             {min(times_per_row):.2f}")
    print(f"  Max:             {max(times_per_row):.2f}")
    if len(times_per_row) > 1:
        print(f"  Std Dev:          {statistics.stdev(times_per_row):.2f}")
    print()
    print("Total time (s):")
    print(f"  Average:        {statistics.mean(total_times):.3f}")
    print(f"  Median:         {statistics.median(total_times):.3f}")
    print(f"  Min:            {min(total_times):.3f}")
    print(f"  Max:            {max(total_times):.3f}")
    if len(total_times) > 1:
        print(f"  Std Dev:         {statistics.stdev(total_times):.3f}")
    print()
    print("=" * 70)
    print("✅ Benchmark complete!")
    print(f"   Average throughput: {statistics.mean(throughputs):,.0f} rows/s")
    print(f"   Data volume per row: {NUM_COLUMNS * 4:,} bytes (1000 × 4-byte INTs)")
    print("=" * 70)


if __name__ == "__main__":
    main()
