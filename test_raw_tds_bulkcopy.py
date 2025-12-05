#!/usr/bin/env python
"""
Benchmark Python-side TDS serialization for bulk copy.

This test pre-serializes data to TDS wire format in Python, then passes
the raw bytes to Rust. This eliminates ALL type conversion overhead.
"""

import os
# Disable tracing for accurate performance measurement
os.environ['RUST_LOG'] = 'error'

import time
from tds_serializer import TdsSerializer
import mssql_python

# Test configuration
SERVER = "localhost"
USER = "sa"
with open("/tmp/password", "r") as f:
    PASSWORD = f.read().strip()
DATABASE = "master"

TABLE_NAME = "benchmark_raw_tds"
NUM_ROWS = 500_000


def test_raw_tds_serialization():
    """Test bulk copy with Python-side TDS serialization."""
    
    # Connect to database (using standard mssql_python API)
    conn_str = f"Server={SERVER};Database={DATABASE};UID={USER};PWD={PASSWORD}"
    print(f"Connecting to database...")
    connection = mssql_python.connect(conn_str)
    cursor = connection.cursor()
    
    # Create test table
    print(f"Creating table {TABLE_NAME}...")
    cursor.execute(f"IF OBJECT_ID('{TABLE_NAME}', 'U') IS NOT NULL DROP TABLE {TABLE_NAME}")
    cursor.execute(f"""
        CREATE TABLE {TABLE_NAME} (
            id INT,
            name NVARCHAR(100),
            active INT,
            score FLOAT
        )
    """)
    connection.commit()  # Commit so the table is visible to other connections
    
    # Define schema for TDS serializer
    column_types = ['INT', 'NVARCHAR', 'INT', 'FLOAT']
    serializer = TdsSerializer(column_types)
    
    # Generate test data
    print(f"Generating {NUM_ROWS} test rows...")
    rows_data = [
        [i, f"Name_{i}", i % 2, i * 1.5]
        for i in range(NUM_ROWS)
    ]
    
    # Pre-serialize all rows to TDS format
    print("Pre-serializing rows to TDS wire format...")
    start_serialize = time.perf_counter()
    serialized_rows = [serializer.serialize_row(row) for row in rows_data]
    serialize_time = time.perf_counter() - start_serialize
    print(f"  Serialization took {serialize_time:.3f}s")
    print(f"  Average: {serialize_time * 1_000_000 / NUM_ROWS:.2f} µs per row")
    
    # Bulk inserting using pre-serialized bytes
    # Direct call to Rust module (similar to how cursor.bulkcopy works internally)
    print(f"\nBulk inserting with pre-serialized TDS bytes (batch_size=0)...")
    print(f"  Total rows: {len(serialized_rows):,}")
    print(f"  Columns: {len(column_types)}")
    print(f"  First row bytes (hex): {serialized_rows[0][:60].hex()}")
    print(f"  First row length: {len(serialized_rows[0])} bytes")
    
    # Test with all rows (not just 100)
    test_rows = serialized_rows
    print(f"  Bulk inserting {len(test_rows):,} rows...")
    
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
        
        # Call write_to_server_raw on the Rust cursor directly
        start = time.perf_counter()
        
        # Create column mappings: list of tuples (source_ordinal, destination_name)
        column_mappings = [
            (0, "id"),
            (1, "name"),
            (2, "active"),
            (3, "score"),
        ]
        
        result = core_cursor.write_to_server_raw(
            table_name=TABLE_NAME,
            rows=test_rows,
            column_count=len(column_types),
            kwargs={"batch_size": 0, "timeout": 60, "column_mappings": column_mappings}  # 60 second timeout for 500k rows
        )
        
        elapsed = time.perf_counter() - start
    finally:
        if core_connection is not None:
            try:
                core_connection.close()
            except Exception:
                pass
    
    # Print results
    rows_copied = result["rows_copied"]
    throughput = rows_copied / elapsed
    
    print(f"\nResults:")
    print(f"  Rows copied: {rows_copied:,}")
    print(f"  Time: {elapsed:.3f}s")
    print(f"  Throughput: {throughput:,.0f} rows/s")
    print(f"  Time per row: {elapsed * 1_000_000 / rows_copied:.2f} µs")
    
    # Verify data
    cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    count = cursor.fetchone()[0]
    print(f"\nVerification:")
    print(f"  Rows in table: {count:,}")
    assert count == len(test_rows), f"Expected {len(test_rows)} rows, got {count}"
    
    # Sample data
    cursor.execute(f"SELECT TOP 3 * FROM {TABLE_NAME}")
    print(f"  Sample rows:")
    for row in cursor.fetchall():
        print(f"    {row}")
    
    # Cleanup
    cursor.execute(f"DROP TABLE {TABLE_NAME}")
    cursor.close()
    connection.close()
    
    print(f"\n✅ Test passed!")
    print(f"   Total throughput: {throughput:,.0f} rows/s")
    print(f"   (Including {serialize_time:.3f}s Python serialization)")


if __name__ == "__main__":
    test_raw_tds_serialization()
