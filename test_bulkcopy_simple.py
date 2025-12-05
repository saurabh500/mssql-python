"""
Simple test script for bulkcopy functionality with iterator and column mappings.
This demonstrates the correct usage of cursor.bulkcopy() method.

Architecture:
- Regular cursor.execute() uses ODBC connection (default backend)
- cursor.bulkcopy() internally creates a temporary Core TDS connection for the bulk operation
- After bulkcopy completes, the temporary Core TDS connection is automatically closed
- Verification queries use the original ODBC connection

Key Requirements:
1. data_source must be an iterator (e.g., list, generator, or df.itertuples())
2. column_mappings must be provided: [(source_ordinal, dest_column_name), ...]
3. Commit DDL changes before bulkcopy to avoid table locks
"""

import mssql_python
import pandas as pd

# Connection string
conn_str = 'Server=localhost;Database=master;UID=sa;PWD=aH7dQGjYpW+GMwRR'

# Create ODBC connection (default backend)
connection = mssql_python.connect(conn_str)
cursor = connection.cursor()

try:
    # Create test table using ODBC connection
    print('Creating table using ODBC connection...')
    cursor.execute('DROP TABLE IF EXISTS BulkCopyTest')
    cursor.execute('CREATE TABLE BulkCopyTest (id INT, name NVARCHAR(100))')
    connection.commit()  # Commit the DDL changes

    # Prepare data - DataFrame
    df = pd.DataFrame({'id': [1, 2, 3, 4, 5], 'name': ['Alice', 'Bob', 'Charlie', 'David', 'Eve']})
    
    # Convert DataFrame to iterator (required by bulkcopy API)
    # itertuples with index=False and name=None returns plain tuples
    data_iter = df.itertuples(index=False, name=None)
    
    # Define column mappings (required)
    # Format: [(source_ordinal, dest_column_name), ...]
    # Source ordinal 0 maps to 'id', source ordinal 1 maps to 'name'
    column_mappings = [(0, 'id'), (1, 'name')]
    
    # Call bulkcopy - this will internally create a temporary Core TDS connection
    print('Calling bulkcopy (will use temporary Core TDS connection)...')
    result = cursor.bulkcopy('BulkCopyTest', data_iter, column_mappings=column_mappings)
    
    print(f'Success! Bulk copy result: {result}')
    
    # Verify data was inserted using ODBC connection
    print('Verifying data using ODBC connection...')
    cursor.execute('SELECT COUNT(*) FROM BulkCopyTest')
    row = cursor.fetchone()
    count = row[0] if row else 0
    print(f'Rows in table: {count}')
    
    # Fetch and display data using ODBC connection
    cursor.execute('SELECT * FROM BulkCopyTest ORDER BY id')
    rows = cursor.fetchall()
    print('Data in table:')
    for row in rows:
        print(f'  id={row[0]}, name={row[1]}')

finally:
    connection.close()
    print('Connection closed.')
