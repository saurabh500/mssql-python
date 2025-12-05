"""
Detailed performance analysis for bulkcopy with different optimizations.

This test identifies specific bottlenecks:
1. Python iterator collection overhead
2. Data conversion overhead
3. Batch size impact
4. GIL contention
"""

import os
# Disable tracing for accurate performance measurement
# Must be set before importing mssql_python
os.environ['RUST_LOG'] = 'error'  # Only show errors, not info/debug traces

import mssql_python
import time
import gc

# Connection string
conn_str = 'Server=localhost;Database=master;UID=sa;PWD=aH7dQGjYpW+GMwRR'

def create_table(cursor):
    """Create test table."""
    cursor.execute('DROP TABLE IF EXISTS BulkCopyOptTest')
    cursor.execute('''
        CREATE TABLE BulkCopyOptTest (
            id INT PRIMARY KEY,
            name NVARCHAR(100),
            value1 INT,
            value2 INT,
            value3 INT,
            value4 INT
        )
    ''')

def test_batch_sizes(cursor, num_rows=1_000_000):
    """Test different batch sizes to find optimal configuration."""
    print('\n' + '='*70)
    print('TEST 1: BATCH SIZE OPTIMIZATION')
    print('='*70)
    
    # Generate data once
    print(f'Generating {num_rows:,} rows...')
    start = time.time()
    data = [(i, f'U{i:07d}', i%100, i%1000, i*10, i*100) for i in range(1, num_rows + 1)]
    gen_time = time.time() - start
    print(f'Data generation: {gen_time:.2f}s\n')
    
    column_mappings = [(0, 'id'), (1, 'name'), (2, 'value1'), (3, 'value2'), (4, 'value3'), (5, 'value4')]
    
    batch_sizes = [0, 1000, 5000, 10000, 25000, 50000]
    results = []
    
    for batch_size in batch_sizes:
        cursor.execute('TRUNCATE TABLE BulkCopyOptTest')
        cursor.connection.commit()
        
        gc.collect()  # Clean memory before test
        
        print(f'Testing batch_size={batch_size if batch_size > 0 else "default"}...')
        start = time.time()
        
        result = cursor.bulkcopy(
            'BulkCopyOptTest',
            iter(data),
            column_mappings=column_mappings,
            batch_size=batch_size,
            table_lock=True
        )
        
        wall_time = time.time() - start
        throughput = num_rows / wall_time
        
        print(f'  Wall time: {wall_time:.3f}s')
        print(f'  Throughput: {throughput:,.0f} rows/s')
        print(f'  Internal time: {result["elapsed_time"]:.3f}s')
        print(f'  Batches: {result["batch_count"]}\n')
        
        results.append({
            'batch_size': batch_size if batch_size > 0 else 'default',
            'wall_time': wall_time,
            'throughput': throughput,
            'internal_time': result['elapsed_time'],
            'batch_count': result['batch_count']
        })
    
    # Find best
    best = max(results, key=lambda x: x['throughput'])
    best_batch_size = batch_sizes[results.index(best)]  # Get the actual integer value
    print(f'BEST BATCH SIZE: {best["batch_size"]} ({best["throughput"]:,.0f} rows/s)')
    
    return results, best_batch_size

def test_data_generation_overhead(num_rows=1_000_000):
    """Measure overhead of different data generation strategies."""
    print('\n' + '='*70)
    print('TEST 2: DATA GENERATION OVERHEAD')
    print('='*70)
    
    # Test 1: List comprehension (what we use)
    print('\n1. List comprehension (current approach):')
    start = time.time()
    data1 = [(i, f'U{i:07d}', i%100, i%1000, i*10, i*100) for i in range(1, num_rows + 1)]
    time1 = time.time() - start
    print(f'   Time: {time1:.3f}s ({num_rows/time1:,.0f} rows/s)')
    
    # Test 2: Pre-allocated with simple formatting
    print('\n2. Pre-computed strings (optimized):')
    start = time.time()
    data2 = []
    for i in range(1, num_rows + 1):
        data2.append((i, f'U{i:07d}', i%100, i%1000, i*10, i*100))
    time2 = time.time() - start
    print(f'   Time: {time2:.3f}s ({num_rows/time2:,.0f} rows/s)')
    
    # Test 3: Generator (lazy - no upfront cost)
    print('\n3. Generator (lazy evaluation):')
    start = time.time()
    def gen():
        for i in range(1, num_rows + 1):
            yield (i, f'U{i:07d}', i%100, i%1000, i*10, i*100)
    gen_obj = gen()
    time3 = time.time() - start
    print(f'   Time: {time3:.6f}s (lazy - no materialization)')
    
    print(f'\nConclusion: List comprehension overhead: {time1:.3f}s for {num_rows:,} rows')
    
    return data1

def test_iterator_collection_overhead(cursor, data, best_batch_size):
    """Test overhead of iterator collection in Rust."""
    print('\n' + '='*70)
    print('TEST 3: ITERATOR COLLECTION OVERHEAD')
    print('='*70)
    
    num_rows = len(data)
    column_mappings = [(0, 'id'), (1, 'name'), (2, 'value1'), (3, 'value2'), (4, 'value3'), (5, 'value4')]
    
    print(f'\nUsing best batch size: {best_batch_size}')
    
    # Test multiple times to get average
    times = []
    for run in range(3):
        cursor.execute('TRUNCATE TABLE BulkCopyOptTest')
        cursor.connection.commit()
        gc.collect()
        
        print(f'\nRun {run + 1}/3:')
        start = time.time()
        
        result = cursor.bulkcopy(
            'BulkCopyOptTest',
            iter(data),
            column_mappings=column_mappings,
            batch_size=best_batch_size,
            table_lock=True
        )
        
        wall_time = time.time() - start
        throughput = num_rows / wall_time
        
        print(f'  Wall time: {wall_time:.3f}s')
        print(f'  Internal time: {result["elapsed_time"]:.3f}s')
        print(f'  Throughput: {throughput:,.0f} rows/s')
        
        overhead = wall_time - result['elapsed_time']
        overhead_pct = (overhead / wall_time) * 100
        print(f'  Overhead: {overhead:.3f}s ({overhead_pct:.1f}%)')
        
        times.append({
            'wall_time': wall_time,
            'internal_time': result['elapsed_time'],
            'throughput': throughput,
            'overhead': overhead,
            'overhead_pct': overhead_pct
        })
    
    avg_throughput = sum(t['throughput'] for t in times) / len(times)
    avg_overhead_pct = sum(t['overhead_pct'] for t in times) / len(times)
    
    print(f'\nAverage throughput: {avg_throughput:,.0f} rows/s')
    print(f'Average overhead: {avg_overhead_pct:.1f}%')
    
    return avg_throughput

def test_with_fewer_columns(cursor):
    """Test if column count affects performance."""
    print('\n' + '='*70)
    print('TEST 4: COLUMN COUNT IMPACT')
    print('='*70)
    
    num_rows = 1_000_000
    
    # Test with 2 columns
    cursor.execute('DROP TABLE IF EXISTS BulkCopyTwoCol')
    cursor.execute('CREATE TABLE BulkCopyTwoCol (id INT PRIMARY KEY, name NVARCHAR(100))')
    cursor.connection.commit()
    
    print(f'\n2 columns test ({num_rows:,} rows):')
    data2 = [(i, f'U{i:07d}') for i in range(1, num_rows + 1)]
    start = time.time()
    result = cursor.bulkcopy(
        'BulkCopyTwoCol',
        iter(data2),
        column_mappings=[(0, 'id'), (1, 'name')],
        batch_size=10000,
        table_lock=True
    )
    time2 = time.time() - start
    throughput2 = num_rows / time2
    print(f'  Throughput: {throughput2:,.0f} rows/s')
    
    # Test with 6 columns
    cursor.execute('TRUNCATE TABLE BulkCopyOptTest')
    cursor.connection.commit()
    
    print(f'\n6 columns test ({num_rows:,} rows):')
    data6 = [(i, f'U{i:07d}', i%100, i%1000, i*10, i*100) for i in range(1, num_rows + 1)]
    start = time.time()
    result = cursor.bulkcopy(
        'BulkCopyOptTest',
        iter(data6),
        column_mappings=[(0, 'id'), (1, 'name'), (2, 'value1'), (3, 'value2'), (4, 'value3'), (5, 'value4')],
        batch_size=10000,
        table_lock=True
    )
    time6 = time.time() - start
    throughput6 = num_rows / time6
    print(f'  Throughput: {throughput6:,.0f} rows/s')
    
    print(f'\nImpact: {(throughput2/throughput6 - 1)*100:.1f}% throughput difference')
    
    cursor.execute('DROP TABLE IF EXISTS BulkCopyTwoCol')

def main():
    print('='*70)
    print('BULKCOPY PERFORMANCE OPTIMIZATION ANALYSIS')
    print('='*70)
    print('\nTarget: 750,000 rows/s (pure Rust performance)')
    print('Current: ~228,000 rows/s (Python binding)')
    print('Gap: ~3.3x slower\n')
    
    connection = mssql_python.connect(conn_str)
    cursor = connection.cursor()
    
    try:
        create_table(cursor)
        connection.commit()
        
        # Test 1: Find optimal batch size
        batch_results, best_batch = test_batch_sizes(cursor)
        
        # Test 2: Measure data generation overhead
        data = test_data_generation_overhead()
        
        # Test 3: Measure iterator collection overhead
        best_throughput = test_iterator_collection_overhead(cursor, data, best_batch)
        
        # Test 4: Column count impact
        test_with_fewer_columns(cursor)
        
        # Final analysis
        print('\n' + '='*70)
        print('BOTTLENECK ANALYSIS')
        print('='*70)
        
        print(f'\nCurrent best throughput: {best_throughput:,.0f} rows/s')
        print(f'Target (pure Rust): 750,000 rows/s')
        print(f'Performance gap: {750_000/best_throughput:.2f}x\n')
        
        print('Identified bottlenecks:')
        print('1. Python iterator collection (happens with GIL)')
        print('2. PythonRowAdapter conversion overhead')
        print('3. All rows materialized in memory before bulk insert starts')
        print('4. String formatting in Python (f-strings)')
        
        print('\nRecommendations:')
        print('1. Stream rows directly without full collection')
        print('2. Optimize PythonRowAdapter to minimize conversions')
        print('3. Use batch_size=10000-25000 for best throughput')
        print('4. Pre-generate strings or use simpler formatting')
        print('5. Consider native Rust data generation for benchmarks')
        
    finally:
        cursor.close()
        connection.close()

if __name__ == '__main__':
    main()
