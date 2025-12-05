"""
Large-scale test for bulkcopy functionality using 1 million rows from Parquet file.
This test demonstrates performance with realistic data volumes.

Architecture:
- Generate 1M rows and save to Parquet file
- Regular cursor.execute() uses ODBC connection (default backend)
- cursor.bulkcopy() internally creates a temporary Core TDS connection for the bulk operation
- Verification queries use the original ODBC connection
"""

import mssql_python
import pandas as pd
import numpy as np
import time
import os

# Connection string
conn_str = 'Server=localhost;Database=master;UID=sa;PWD=aH7dQGjYpW+GMwRR'

# File path for parquet
parquet_file = '/tmp/test_data_1m.parquet'

# Step 1: Generate large dataset and save to Parquet
print('Step 1: Generating 1 million rows...')
start_gen = time.time()

# Generate realistic data
np.random.seed(42)
num_rows = 1_000_000

# Use Python int() and float() for better compatibility
# For now, use INT for all numeric types as other types need Rust support
np.random.seed(42)

data = {
    'id': list(range(1, num_rows + 1)),
    'name': [f'User_{i:07d}' for i in range(1, num_rows + 1)],
    'age': [int(x) for x in np.random.randint(18, 80, size=num_rows)],
    'score': [int(x) for x in np.random.randint(0, 1000, size=num_rows)],
    'revenue': [int(x) for x in np.random.randint(1000, 999999, size=num_rows)],
    'views': [int(x) for x in np.random.randint(0, 10000000, size=num_rows)]
}

df = pd.DataFrame(data)
gen_time = time.time() - start_gen
print(f'Generated {len(df):,} rows in {gen_time:.2f} seconds')

# Save to Parquet
print(f'Saving to Parquet file: {parquet_file}')
start_save = time.time()
df.to_parquet(parquet_file, compression='snappy', index=False)
save_time = time.time() - start_save
file_size_mb = os.path.getsize(parquet_file) / (1024 * 1024)
print(f'Saved to Parquet in {save_time:.2f} seconds ({file_size_mb:.2f} MB)')

# Step 2: Create connection and table
print('\nStep 2: Creating table using ODBC connection...')
connection = mssql_python.connect(conn_str)
cursor = connection.cursor()

try:
    cursor.execute('DROP TABLE IF EXISTS BulkCopyLargeTest')
    cursor.execute('''
        CREATE TABLE BulkCopyLargeTest (
            id INT PRIMARY KEY,
            name NVARCHAR(100),
            age INT,
            score INT,
            revenue INT,
            views INT
        )
    ''')
    connection.commit()
    print('Table created successfully')

    # Step 3: Load Parquet and prepare iterator
    print('\nStep 3: Loading Parquet file...')
    start_load = time.time()
    df_loaded = pd.read_parquet(parquet_file)
    load_time = time.time() - start_load
    print(f'Loaded {len(df_loaded):,} rows in {load_time:.2f} seconds')

    # Convert to iterator
    print('Converting DataFrame to iterator...')
    data_iter = df_loaded.itertuples(index=False, name=None)
    
    # Define column mappings
    column_mappings = [
        (0, 'id'),
        (1, 'name'),
        (2, 'age'),
        (3, 'score'),
        (4, 'revenue'),
        (5, 'views')
    ]
    
    # Step 4: Perform bulk copy
    print('\nStep 4: Performing bulk copy (this will use temporary Core TDS connection)...')
    start_bcp = time.time()
    result = cursor.bulkcopy(
        'BulkCopyLargeTest',
        data_iter,
        column_mappings=column_mappings,
        batch_size=0,  # 10k rows per batch
        table_lock=True    # Use table lock for better performance
    )
    bcp_time = time.time() - start_bcp
    
    print(f'\n✓ Bulk copy completed!')
    print(f'  Rows copied: {result["rows_copied"]:,}')
    print(f'  Batch count: {result["batch_count"]}')
    print(f'  Elapsed time: {result["elapsed_time"]:.2f} seconds')
    print(f'  Throughput: {result["rows_per_second"]:,.0f} rows/second')
    print(f'  Wall clock time: {bcp_time:.2f} seconds')
    
    # Step 5: Verify data using ODBC connection
    print('\nStep 5: Verifying data using ODBC connection...')
    
    # Check row count
    cursor.execute('SELECT COUNT(*) FROM BulkCopyLargeTest')
    count = cursor.fetchone()[0]
    print(f'  Total rows in table: {count:,}')
    
    # Check some statistics
    cursor.execute('''
        SELECT 
            MIN(id) as min_id,
            MAX(id) as max_id,
            MIN(age) as min_age,
            MAX(age) as max_age,
            AVG(CAST(score AS FLOAT)) as avg_score,
            SUM(CAST(revenue AS BIGINT)) as total_revenue,
            MAX(views) as max_views,
            COUNT(*) as total_count
        FROM BulkCopyLargeTest
    ''')
    stats = cursor.fetchone()
    print(f'  ID range: {stats[0]:,}-{stats[1]:,}')
    print(f'  Age range: {stats[2]}-{stats[3]}')
    print(f'  Average score: {stats[4]:.2f}')
    print(f'  Total revenue: ${stats[5]:,}')
    print(f'  Max views: {stats[6]:,}')
    print(f'  Total count: {stats[7]:,}')
    
    # Sample some rows
    print('\nSample rows:')
    cursor.execute('SELECT TOP 5 id, name, age, score, revenue, views FROM BulkCopyLargeTest ORDER BY id')
    rows = cursor.fetchall()
    for row in rows:
        print(f'  ID: {row[0]}, Name: {row[1]}, Age: {row[2]}, Score: {row[3]}, Revenue: ${row[4]:,}, Views: {row[5]:,}')
    
    # Verify data integrity
    print('\nVerifying data integrity...')
    if count == num_rows:
        print(f'  ✓ Row count matches: {count:,} rows')
    else:
        print(f'  ✗ Row count mismatch! Expected {num_rows:,}, got {count:,}')
    
    # Performance summary
    print('\n' + '='*60)
    print('PERFORMANCE SUMMARY')
    print('='*60)
    print(f'Data generation:    {gen_time:.2f}s')
    print(f'Parquet save:       {save_time:.2f}s')
    print(f'Parquet load:       {load_time:.2f}s')
    print(f'Bulk copy:          {bcp_time:.2f}s ({result["rows_per_second"]:,.0f} rows/s)')
    print(f'Total time:         {gen_time + save_time + load_time + bcp_time:.2f}s')
    print('='*60)

finally:
    cursor.close()
    connection.close()
    print('\nConnection closed.')
    
    # Cleanup parquet file
    if os.path.exists(parquet_file):
        os.remove(parquet_file)
        print(f'Cleaned up {parquet_file}')
