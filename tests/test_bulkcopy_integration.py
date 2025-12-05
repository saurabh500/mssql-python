"""
Integration tests for cursor.bulkcopy() method.

These tests verify the bulk copy functionality using the Core TDS backend.
"""

import pytest
import datetime
import os
from decimal import Decimal
from mssql_python import connect, set_backend


@pytest.fixture(scope="module")
def connection_string():
    """Provide connection string for tests."""
    # Use environment variable if available, otherwise use default
    return os.environ.get(
        'MSSQL_CONNECTION_STRING', 
        "Server=localhost;Database=master;UID=sa;PWD={YourStrong@Passw0rd}"
    )


@pytest.fixture(scope="module")
def connection(connection_string):
    """Create a connection for testing (can use any backend)."""
    # bulkcopy() will create its own temporary Core TDS connection
    # so we can use the default ODBC backend for setup/teardown
    conn = connect(connection_string)
    yield conn
    conn.close()


@pytest.fixture
def cursor(connection):
    """Create a cursor for each test."""
    cur = connection.cursor()
    yield cur
    cur.close()


@pytest.fixture
def test_table(cursor):
    """Create a test table for bulk copy operations."""
    table_name = "BulkCopyTestTable"
    
    # Drop table if exists
    cursor.execute(f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL DROP TABLE {table_name}")
    
    # Create test table
    cursor.execute(f"""
        CREATE TABLE {table_name} (
            id INT PRIMARY KEY,
            name NVARCHAR(100),
            value DECIMAL(10, 2),
            created_date DATETIME
        )
    """)
    
    yield table_name
    
    # Cleanup
    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")


class TestBulkCopyBasic:
    """Basic bulk copy tests."""
    
    def test_simple_bulkcopy(self, cursor, test_table):
        """Test simple bulk copy with small dataset."""
        data = [
            (1, 'Alice', Decimal('100.50'), datetime.datetime(2024, 1, 1)),
            (2, 'Bob', Decimal('200.75'), datetime.datetime(2024, 1, 2)),
            (3, 'Charlie', Decimal('300.25'), datetime.datetime(2024, 1, 3)),
        ]
        
        result = cursor.bulkcopy(test_table, data)
        
        assert result['rows_copied'] == 3
        assert result['batch_count'] >= 1
        assert result['elapsed_time'] > 0
        assert result['rows_per_second'] > 0
        
        # Verify data was inserted
        cursor.execute(f"SELECT COUNT(*) FROM {test_table}")
        count = cursor.fetchone()[0]
        assert count == 3
    
    def test_bulkcopy_with_batch_size(self, cursor, test_table):
        """Test bulk copy with custom batch size."""
        data = [(i, f'User{i}', Decimal(i * 10.5), datetime.datetime.now()) 
                for i in range(1, 101)]
        
        result = cursor.bulkcopy(test_table, data, batch_size=25)
        
        assert result['rows_copied'] == 100
        assert result['batch_count'] == 4  # 100 rows / 25 per batch
    
    def test_bulkcopy_with_iterator(self, cursor, test_table):
        """Test bulk copy with generator iterator."""
        def data_generator():
            for i in range(1, 51):
                yield (i, f'Generated{i}', Decimal(i * 5.0), datetime.datetime.now())
        
        result = cursor.bulkcopy(test_table, data_generator())
        
        assert result['rows_copied'] == 50


class TestBulkCopyOptions:
    """Tests for bulk copy options."""
    
    def test_bulkcopy_with_table_lock(self, cursor, test_table):
        """Test bulk copy with table lock option."""
        data = [(i, f'User{i}', Decimal(100), datetime.datetime.now()) 
                for i in range(1, 11)]
        
        result = cursor.bulkcopy(test_table, data, table_lock=True)
        
        assert result['rows_copied'] == 10
    
    def test_bulkcopy_with_timeout(self, cursor, test_table):
        """Test bulk copy with custom timeout."""
        data = [(1, 'Test', Decimal(100), datetime.datetime.now())]
        
        result = cursor.bulkcopy(test_table, data, timeout=60)
        
        assert result['rows_copied'] == 1


class TestBulkCopyColumnMappings:
    """Tests for column mapping functionality."""
    
    def test_bulkcopy_with_name_mappings(self, cursor):
        """Test bulk copy with column name mappings."""
        # Create table with different column names
        cursor.execute("""
            IF OBJECT_ID('MappingTest', 'U') IS NOT NULL DROP TABLE MappingTest
        """)
        cursor.execute("""
            CREATE TABLE MappingTest (
                user_id INT PRIMARY KEY,
                user_name NVARCHAR(100)
            )
        """)
        
        try:
            data = [(1, 'Alice'), (2, 'Bob')]
            
            # Map source columns to destination columns by name
            result = cursor.bulkcopy(
                'MappingTest',
                data,
                column_mappings=[('id', 'user_id'), ('name', 'user_name')]
            )
            
            assert result['rows_copied'] == 2
        finally:
            cursor.execute("DROP TABLE IF EXISTS MappingTest")
    
    def test_bulkcopy_with_ordinal_mappings(self, cursor):
        """Test bulk copy with column ordinal mappings."""
        cursor.execute("""
            IF OBJECT_ID('OrdinalTest', 'U') IS NOT NULL DROP TABLE OrdinalTest
        """)
        cursor.execute("""
            CREATE TABLE OrdinalTest (
                col1 INT,
                col2 NVARCHAR(50)
            )
        """)
        
        try:
            data = [(1, 'First'), (2, 'Second')]
            
            # Map by ordinal position (0-based)
            result = cursor.bulkcopy(
                'OrdinalTest',
                data,
                column_mappings=[(0, 'col1'), (1, 'col2')]
            )
            
            assert result['rows_copied'] == 2
        finally:
            cursor.execute("DROP TABLE IF EXISTS OrdinalTest")


class TestBulkCopyDataFrames:
    """Tests for bulk copy with pandas DataFrames."""
    
    @pytest.mark.skipif(
        not pytest.importorskip("pandas"),
        reason="pandas not installed"
    )
    def test_bulkcopy_from_dataframe(self, cursor, test_table):
        """Test bulk copy from pandas DataFrame."""
        import pandas as pd
        
        df = pd.DataFrame({
            'id': range(1, 11),
            'name': [f'User{i}' for i in range(1, 11)],
            'value': [Decimal(i * 10.0) for i in range(1, 11)],
            'created_date': [datetime.datetime.now() for _ in range(1, 11)]
        })
        
        # Use itertuples() which returns tuple iterator
        result = cursor.bulkcopy(test_table, df.itertuples(index=False, name=None))
        
        assert result['rows_copied'] == 10


class TestBulkCopyErrors:
    """Tests for error handling."""
    
    def test_bulkcopy_table_not_found(self, cursor):
        """Test bulk copy with non-existent table."""
        data = [(1, 'Test')]
        
        with pytest.raises(Exception):
            cursor.bulkcopy('NonExistentTable', data)
    
    def test_bulkcopy_closed_cursor(self, connection):
        """Test bulk copy on closed cursor."""
        cursor = connection.cursor()
        cursor.close()
        
        with pytest.raises(Exception):
            cursor.bulkcopy('TestTable', [(1, 'Test')])


class TestBulkCopyPerformance:
    """Performance tests for bulk copy."""
    
    @pytest.mark.slow
    def test_bulkcopy_large_dataset(self, cursor, test_table):
        """Test bulk copy with large dataset (10k rows)."""
        data = [(i, f'User{i}', Decimal(i * 10.0), datetime.datetime.now()) 
                for i in range(1, 10001)]
        
        result = cursor.bulkcopy(test_table, data, batch_size=5000)
        
        assert result['rows_copied'] == 10000
        assert result['batch_count'] == 2
        assert result['rows_per_second'] > 1000  # Should be fast
    
    @pytest.mark.slow
    def test_bulkcopy_performance_comparison(self, cursor, test_table):
        """Compare bulk copy performance with regular INSERT."""
        import time
        
        # Test bulk copy
        data = [(i, f'User{i}', Decimal(100), datetime.datetime.now()) 
                for i in range(1, 1001)]
        
        start = time.time()
        result = cursor.bulkcopy(test_table, data)
        bulk_time = time.time() - start
        
        cursor.execute(f"DELETE FROM {test_table}")
        
        # Test regular INSERT (for comparison)
        start = time.time()
        for row in data:
            cursor.execute(
                f"INSERT INTO {test_table} (id, name, value, created_date) VALUES (?, ?, ?, ?)",
                row
            )
        insert_time = time.time() - start
        
        # Bulk copy should be significantly faster
        assert bulk_time < insert_time * 0.5  # At least 2x faster


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
