    #!/usr/bin/env python3
"""
Benchmark fast-path optimization multiple times to get average throughput.
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
TABLE_NAME = "benchmark_fastpath"
NUM_ROWS = 500_000
NUM_RUNS = 10


def run_single_test():
    """Run a single bulkcopy test and return throughput."""
    conn_str = f"Server={SERVER};Database={DATABASE};UID={USER};PWD={PASSWORD}"
    connection = mssql_python.connect(conn_str)
    cursor = connection.cursor()
    
    # Create table
    cursor.execute(f"IF OBJECT_ID('{TABLE_NAME}', 'U') IS NOT NULL DROP TABLE {TABLE_NAME}")
    cursor.execute(f"""
        CREATE TABLE {TABLE_NAME} (
            id INT,
            name NVARCHAR(2048),
            active INT,
            score FLOAT
        )
    """)
    connection.commit()
    
    # Generate test data - Use 1KB strings to test string conversion performance
    large_string = "X" * 1024  # 1KB string
    rows_data = [
        (i, f"{large_string}_{i}", i % 2, i * 1.5)
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
        
        # Column mappings
        column_mappings = [
            (0, "id"),
            (1, "name"),
            (2, "active"),
            (3, "score"),
        ]
        
        # Bulk insert with fast-path optimization (using regular bulkcopy which has fast-path enabled)
        start = time.perf_counter()
        
        result = core_cursor.bulkcopy(
            TABLE_NAME,
            iter(rows_data),
            {"batch_size": 0, "timeout": 60, "column_mappings": column_mappings}
        )
        
        elapsed = time.perf_counter() - start
        
    finally:
        if core_connection is not None:
            try:
                core_connection.close()
            except Exception:
                pass
    
    # Verify
    cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    count = cursor.fetchone()[0]
    
    # Cleanup
    cursor.execute(f"DROP TABLE {TABLE_NAME}")
    cursor.close()
    connection.close()
    
    if count != NUM_ROWS:
        raise RuntimeError(f"Expected {NUM_ROWS} rows, got {count}")
    
    throughput = NUM_ROWS / elapsed
    time_per_row = elapsed * 1_000_000 / NUM_ROWS
    
    return throughput, time_per_row, elapsed


def main():
    """Run benchmark multiple times and report statistics."""
    print(f"Fast-Path Bulkcopy Benchmark")
    print(f"{'='*70}")
    print(f"Configuration:")
    print(f"  Rows per test: {NUM_ROWS:,}")
    print(f"  Number of runs: {NUM_RUNS}")
    print(f"  Server: {SERVER}")
    print(f"  Database: {DATABASE}")
    print(f"{'='*70}\n")
    
    throughputs = []
    times_per_row = []
    total_times = []
    
    for i in range(NUM_RUNS):
        print(f"Run {i+1}/{NUM_RUNS}...", end=" ", flush=True)
        try:
            throughput, time_per_row, total_time = run_single_test()
            throughputs.append(throughput)
            times_per_row.append(time_per_row)
            total_times.append(total_time)
            print(f"{throughput:,.0f} rows/s ({time_per_row:.2f} µs/row, {total_time:.3f}s total)")
        except Exception as e:
            print(f"FAILED: {e}")
            continue
    
    if not throughputs:
        print("\n❌ All runs failed!")
        return
    
    # Calculate statistics
    print(f"\n{'='*70}")
    print(f"RESULTS ({len(throughputs)} successful runs):")
    print(f"{'='*70}")
    print(f"\nThroughput (rows/s):")
    print(f"  Average:  {statistics.mean(throughputs):>12,.0f}")
    print(f"  Median:   {statistics.median(throughputs):>12,.0f}")
    print(f"  Min:      {min(throughputs):>12,.0f}")
    print(f"  Max:      {max(throughputs):>12,.0f}")
    if len(throughputs) > 1:
        print(f"  Std Dev:  {statistics.stdev(throughputs):>12,.0f}")
    
    print(f"\nTime per row (µs):")
    print(f"  Average:  {statistics.mean(times_per_row):>12.2f}")
    print(f"  Median:   {statistics.median(times_per_row):>12.2f}")
    print(f"  Min:      {min(times_per_row):>12.2f}")
    print(f"  Max:      {max(times_per_row):>12.2f}")
    if len(times_per_row) > 1:
        print(f"  Std Dev:  {statistics.stdev(times_per_row):>12.2f}")
    
    print(f"\nTotal time (s):")
    print(f"  Average:  {statistics.mean(total_times):>12.3f}")
    print(f"  Median:   {statistics.median(total_times):>12.3f}")
    print(f"  Min:      {min(total_times):>12.3f}")
    print(f"  Max:      {max(total_times):>12.3f}")
    if len(total_times) > 1:
        print(f"  Std Dev:  {statistics.stdev(total_times):>12.3f}")
    
    print(f"\n{'='*70}")
    print(f"✅ Benchmark complete!")
    print(f"   Average throughput: {statistics.mean(throughputs):,.0f} rows/s")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
