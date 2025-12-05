#!/usr/bin/env python3
"""Simple test to verify bulkcopy works at all."""

import mssql_python

# Connection details
SERVER = "localhost"
DATABASE = "tempdb"
USER = "sa"
PASSWORD = open("/tmp/password").read().strip()

TABLE_NAME = "test_simple_bcp"

def test_simple():
    """Test basic bulkcopy to ensure it works."""
    
    # Connect
    print(f"Connecting to {SERVER}/{DATABASE}...")
    conn = mssql_python.connect(f"Server={SERVER};Database={DATABASE};UID={USER};PWD={PASSWORD}")
    cursor = conn.cursor()
    
    # Create table
    print(f"Creating table {TABLE_NAME}...")
    cursor.execute(f"IF OBJECT_ID('{TABLE_NAME}', 'U') IS NOT NULL DROP TABLE {TABLE_NAME}")
    cursor.execute(f"""
        CREATE TABLE {TABLE_NAME} (
            id INT,
            name NVARCHAR(100)
        )
    """)
    conn.commit()
    
    # Test data
    print("Preparing 100 rows...")
    rows = [[i, f"Name_{i}"] for i in range(100)]
    
    # Bulkcopy
    print("Calling bulkcopy...")
    cursor.bulkcopy(TABLE_NAME, iter(rows))
    
    # Verify
    cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    count = cursor.fetchone()[0]
    print(f"Success! {count} rows inserted")
    
    # Cleanup
    cursor.close()
    conn.close()

if __name__ == "__main__":
    test_simple()
