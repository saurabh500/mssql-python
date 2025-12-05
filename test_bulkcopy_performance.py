"""
Performance comparison test for bulkcopy functionality.
Tests different data sources to identify bottlenecks and optimization opportunities.

Scenarios:
1. In-memory list (baseline - no I/O overhead)
2. Generator (lazy evaluation)
3. Parquet file (with I/O overhead)
"""

import mssql_python
import pandas as pd
import numpy as np
import time

# Connection string
conn_str = 'Server=localhost;Database=master;UID=sa;PWD=aH7dQGjYpW+GMwRR'

# Test parameters
num_rows = 1_000_000

def generate_test_data(num_rows):
    """Generate test data in memory."""
    print(f'Generating {num_rows:,} rows in memory...')
    start = time.time()
    data = [
        (i, f'User_{i:07d}', i % 100, i % 1000, i * 10, i * 100)
        for i in range(1, num_rows + 1)
    ]
    elapsed = time.time() - start
    print(f'  Generated in {elapsed:.2f}s')
    return data

def data_generator(num_rows):
    """Generator function that yields rows on demand."""
    for i in range(1, num_rows + 1):
        yield (i, f'User_{i:07d}', i % 100, i % 1000, i * 10, i * 100)

def setup_table(cursor):
    """Create test table."""
    cursor.execute('DROP TABLE IF EXISTS BulkCopyPerfTest')
    cursor.execute('''
        CREATE TABLE BulkCopyPerfTest (
            id INT PRIMARY KEY,
            name NVARCHAR(100),
            age INT,
            score INT,
            revenue INT,
            views INT
        )
    ''')

def run_bulkcopy_test(cursor, data_source, test_name, column_mappings):
    """Run a single bulkcopy test."""
    print(f'\n{"="*60}')
    print(f'TEST: {test_name}')
    print(f'{"="*60}')
    
    # Clear table
    cursor.execute('TRUNCATE TABLE BulkCopyPerfTest')
    cursor.connection.commit()
    
    # Run bulkcopy
    print('Running bulkcopy...')
    start = time.time()
    result = cursor.bulkcopy(
        'BulkCopyPerfTest',
        data_source,
        column_mappings=column_mappings,
        batch_size=10000,
        table_lock=True
    )
    wall_clock = time.time() - start
    
    # Verify
    cursor.execute('SELECT COUNT(*) FROM BulkCopyPerfTest')
    count = cursor.fetchone()[0]
    
    print(f'\nResults:')
    print(f'  Rows copied: {result["rows_copied"]:,}')
    print(f'  Batch count: {result["batch_count"]}')
    print(f'  Internal elapsed: {result["elapsed_time"]:.3f}s')
    print(f'  Wall clock time: {wall_clock:.3f}s')
    print(f'  Throughput: {result["rows_per_second"]:,.0f} rows/s')
    print(f'  Wall clock throughput: {result["rows_copied"]/wall_clock:,.0f} rows/s')
    print(f'  Verified count: {count:,}')
    
    return {
        'test_name': test_name,
        'rows_copied': result['rows_copied'],
        'internal_time': result['elapsed_time'],
        'wall_clock_time': wall_clock,
        'throughput': result['rows_per_second'],
        'wall_clock_throughput': result['rows_copied']/wall_clock
    }

def main():
    print('='*60)
    print('BULKCOPY PERFORMANCE COMPARISON')
    print('='*60)
    
    # Column mappings
    column_mappings = [
        (0, 'id'),
        (1, 'name'),
        (2, 'age'),
        (3, 'score'),
        (4, 'revenue'),
        (5, 'views')
    ]
    
    # Connect and setup
    connection = mssql_python.connect(conn_str)
    cursor = connection.cursor()
    
    try:
        setup_table(cursor)
        connection.commit()
        print('Table created successfully')
        
        results = []
        
        # Test 1: In-memory list (pre-materialized)
        print('\n' + '='*60)
        print('Preparing Test 1: In-memory list (pre-materialized)')
        print('='*60)
        data_list = generate_test_data(num_rows)
        result1 = run_bulkcopy_test(cursor, iter(data_list), 
                                     'In-memory list', column_mappings)
        results.append(result1)
        
        # Test 2: Generator (lazy evaluation)
        print('\n' + '='*60)
        print('Preparing Test 2: Generator (lazy evaluation)')
        print('='*60)
        print('Using generator function (no pre-materialization)')
        result2 = run_bulkcopy_test(cursor, data_generator(num_rows),
                                     'Generator', column_mappings)
        results.append(result2)
        
        # Test 3: Parquet file
        print('\n' + '='*60)
        print('Preparing Test 3: Parquet file')
        print('='*60)
        parquet_file = '/tmp/perf_test.parquet'
        
        print('Creating DataFrame and saving to Parquet...')
        start = time.time()
        df = pd.DataFrame(data_list, columns=['id', 'name', 'age', 'score', 'revenue', 'views'])
        df.to_parquet(parquet_file, compression='snappy', index=False)
        save_time = time.time() - start
        print(f'  Saved to Parquet in {save_time:.2f}s')
        
        print('Loading from Parquet...')
        start = time.time()
        df_loaded = pd.read_parquet(parquet_file)
        load_time = time.time() - start
        print(f'  Loaded from Parquet in {load_time:.2f}s')
        
        data_iter = df_loaded.itertuples(index=False, name=None)
        result3 = run_bulkcopy_test(cursor, data_iter,
                                     'Parquet file', column_mappings)
        result3['parquet_save_time'] = save_time
        result3['parquet_load_time'] = load_time
        results.append(result3)
        
        # Cleanup
        import os
        if os.path.exists(parquet_file):
            os.remove(parquet_file)
        
        # Summary comparison
        print('\n' + '='*60)
        print('PERFORMANCE SUMMARY')
        print('='*60)
        print(f'\n{"Test":<25} {"Rows":<15} {"Wall Time":<15} {"Throughput (rows/s)":<20}')
        print('-' * 75)
        
        for r in results:
            print(f'{r["test_name"]:<25} {r["rows_copied"]:>12,}   {r["wall_clock_time"]:>10.3f}s   {r["wall_clock_throughput"]:>18,.0f}')
        
        # Calculate speedups
        baseline = results[0]['wall_clock_throughput']
        print('\n' + '='*60)
        print('RELATIVE PERFORMANCE (vs In-memory list)')
        print('='*60)
        for r in results:
            speedup = r['wall_clock_throughput'] / baseline
            print(f'{r["test_name"]:<25} {speedup:>6.2f}x')
        
        # Analysis
        print('\n' + '='*60)
        print('ANALYSIS')
        print('='*60)
        
        if 'parquet_save_time' in results[2]:
            print(f'\nParquet overhead:')
            print(f'  Save time: {results[2]["parquet_save_time"]:.2f}s')
            print(f'  Load time: {results[2]["parquet_load_time"]:.2f}s')
            print(f'  Total overhead: {results[2]["parquet_save_time"] + results[2]["parquet_load_time"]:.2f}s')
        
        print(f'\nBulkcopy internal vs wall clock:')
        for r in results:
            overhead = r['wall_clock_time'] - r['internal_time']
            overhead_pct = (overhead / r['wall_clock_time']) * 100
            print(f'  {r["test_name"]:<25} Overhead: {overhead:.3f}s ({overhead_pct:.1f}%)')
        
    finally:
        cursor.close()
        connection.close()
        print('\nConnection closed.')

if __name__ == '__main__':
    main()
