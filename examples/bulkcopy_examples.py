"""
Example usage of cursor.bulkcopy() for high-performance data loading.

This demonstrates various ways to use the bulk copy feature with the Core TDS backend.
"""

import datetime
from decimal import Decimal
from mssql_python import connect, set_backend


def example_1_simple_bulkcopy():
    """Example 1: Simple bulk copy with a list of tuples."""
    print("=" * 60)
    print("Example 1: Simple Bulk Copy")
    print("=" * 60)
    
    # Set backend to Core TDS (required for bulk copy)
    set_backend('core')
    
    connection = connect("Server=localhost;Database=testdb;UID=sa;PWD=YourPassword")
    cursor = connection.cursor()
    
    # Create test table
    cursor.execute("""
        IF OBJECT_ID('Users', 'U') IS NOT NULL DROP TABLE Users;
        CREATE TABLE Users (
            id INT PRIMARY KEY,
            name NVARCHAR(100),
            email NVARCHAR(100),
            balance DECIMAL(10, 2),
            created_date DATETIME
        )
    """)
    
    # Prepare data
    data = [
        (1, 'Alice Smith', 'alice@example.com', Decimal('1000.50'), datetime.datetime(2024, 1, 1)),
        (2, 'Bob Johnson', 'bob@example.com', Decimal('2500.75'), datetime.datetime(2024, 1, 2)),
        (3, 'Charlie Brown', 'charlie@example.com', Decimal('500.00'), datetime.datetime(2024, 1, 3)),
    ]
    
    # Bulk copy
    result = cursor.bulkcopy('Users', data)
    
    print(f"✓ Copied {result['rows_copied']} rows in {result['elapsed_time']:.3f} seconds")
    print(f"✓ Throughput: {result['rows_per_second']:.0f} rows/second")
    print(f"✓ Batches: {result['batch_count']}")
    
    cursor.close()
    connection.close()


def example_2_large_dataset():
    """Example 2: Bulk copy with large dataset and custom batch size."""
    print("\n" + "=" * 60)
    print("Example 2: Large Dataset with Batch Size")
    print("=" * 60)
    
    set_backend('core')
    connection = connect("Server=localhost;Database=testdb;UID=sa;PWD=YourPassword")
    cursor = connection.cursor()
    
    # Create test table
    cursor.execute("""
        IF OBJECT_ID('LargeTable', 'U') IS NOT NULL DROP TABLE LargeTable;
        CREATE TABLE LargeTable (
            id INT,
            data NVARCHAR(50),
            value DECIMAL(10, 2)
        )
    """)
    
    # Generate 100,000 rows
    print("Generating 100,000 rows...")
    data = [
        (i, f'Data_{i}', Decimal(i * 1.5))
        for i in range(1, 100001)
    ]
    
    # Bulk copy with larger batch size for better performance
    print("Starting bulk copy...")
    result = cursor.bulkcopy('LargeTable', data, batch_size=10000)
    
    print(f"✓ Copied {result['rows_copied']:,} rows in {result['elapsed_time']:.3f} seconds")
    print(f"✓ Throughput: {result['rows_per_second']:,.0f} rows/second")
    print(f"✓ Batches: {result['batch_count']}")
    
    cursor.close()
    connection.close()


def example_3_generator():
    """Example 3: Using generator for memory-efficient bulk copy."""
    print("\n" + "=" * 60)
    print("Example 3: Memory-Efficient Generator")
    print("=" * 60)
    
    set_backend('core')
    connection = connect("Server=localhost;Database=testdb;UID=sa;PWD=YourPassword")
    cursor = connection.cursor()
    
    # Create test table
    cursor.execute("""
        IF OBJECT_ID('StreamingData', 'U') IS NOT NULL DROP TABLE StreamingData;
        CREATE TABLE StreamingData (
            id INT,
            timestamp DATETIME,
            value FLOAT
        )
    """)
    
    # Generator function - doesn't load all data into memory at once
    def data_generator(count):
        """Generate data on-the-fly."""
        for i in range(1, count + 1):
            yield (i, datetime.datetime.now(), i * 0.5)
            if i % 10000 == 0:
                print(f"  Generated {i:,} rows...")
    
    print("Streaming 50,000 rows from generator...")
    result = cursor.bulkcopy('StreamingData', data_generator(50000), batch_size=5000)
    
    print(f"✓ Copied {result['rows_copied']:,} rows in {result['elapsed_time']:.3f} seconds")
    print(f"✓ Throughput: {result['rows_per_second']:,.0f} rows/second")
    
    cursor.close()
    connection.close()


def example_4_pandas_dataframe():
    """Example 4: Bulk copy from pandas DataFrame."""
    print("\n" + "=" * 60)
    print("Example 4: Pandas DataFrame")
    print("=" * 60)
    
    try:
        import pandas as pd
    except ImportError:
        print("⚠ pandas not installed, skipping this example")
        return
    
    set_backend('core')
    connection = connect("Server=localhost;Database=testdb;UID=sa;PWD=YourPassword")
    cursor = connection.cursor()
    
    # Create test table
    cursor.execute("""
        IF OBJECT_ID('SalesData', 'U') IS NOT NULL DROP TABLE SalesData;
        CREATE TABLE SalesData (
            product_id INT,
            product_name NVARCHAR(100),
            quantity INT,
            price DECIMAL(10, 2),
            sale_date DATETIME
        )
    """)
    
    # Create DataFrame
    df = pd.DataFrame({
        'product_id': range(1, 1001),
        'product_name': [f'Product_{i}' for i in range(1, 1001)],
        'quantity': [i % 100 for i in range(1, 1001)],
        'price': [Decimal(i * 9.99) for i in range(1, 1001)],
        'sale_date': [datetime.datetime.now() for _ in range(1, 1001)]
    })
    
    print(f"DataFrame shape: {df.shape}")
    
    # Bulk copy using itertuples()
    result = cursor.bulkcopy(
        'SalesData',
        df.itertuples(index=False, name=None),
        batch_size=500
    )
    
    print(f"✓ Copied {result['rows_copied']:,} rows in {result['elapsed_time']:.3f} seconds")
    print(f"✓ Throughput: {result['rows_per_second']:,.0f} rows/second")
    
    cursor.close()
    connection.close()


def example_5_column_mappings():
    """Example 5: Using column mappings to match different schemas."""
    print("\n" + "=" * 60)
    print("Example 5: Column Mappings")
    print("=" * 60)
    
    set_backend('core')
    connection = connect("Server=localhost;Database=testdb;UID=sa;PWD=YourPassword")
    cursor = connection.cursor()
    
    # Create table with specific column names
    cursor.execute("""
        IF OBJECT_ID('EmployeeData', 'U') IS NOT NULL DROP TABLE EmployeeData;
        CREATE TABLE EmployeeData (
            emp_id INT PRIMARY KEY,
            emp_name NVARCHAR(100),
            emp_salary DECIMAL(10, 2)
        )
    """)
    
    # Source data has different structure
    source_data = [
        (101, 'John Doe', Decimal('75000.00')),
        (102, 'Jane Smith', Decimal('82000.00')),
        (103, 'Bob Wilson', Decimal('68000.00')),
    ]
    
    # Map source columns to destination columns
    result = cursor.bulkcopy(
        'EmployeeData',
        source_data,
        column_mappings=[
            (0, 'emp_id'),      # First column -> emp_id
            (1, 'emp_name'),    # Second column -> emp_name
            (2, 'emp_salary')   # Third column -> emp_salary
        ]
    )
    
    print(f"✓ Copied {result['rows_copied']} rows with column mappings")
    
    # Verify data
    cursor.execute("SELECT * FROM EmployeeData")
    rows = cursor.fetchall()
    print(f"✓ Verified {len(rows)} rows in destination table")
    
    cursor.close()
    connection.close()


def example_6_identity_columns():
    """Example 6: Inserting explicit identity values."""
    print("\n" + "=" * 60)
    print("Example 6: Identity Columns")
    print("=" * 60)
    
    set_backend('core')
    connection = connect("Server=localhost;Database=testdb;UID=sa;PWD=YourPassword")
    cursor = connection.cursor()
    
    # Create table with identity column
    cursor.execute("""
        IF OBJECT_ID('Products', 'U') IS NOT NULL DROP TABLE Products;
        CREATE TABLE Products (
            product_id INT IDENTITY(1,1) PRIMARY KEY,
            product_name NVARCHAR(100),
            price DECIMAL(10, 2)
        )
    """)
    
    # Insert some initial data
    cursor.execute("INSERT INTO Products (product_name, price) VALUES ('Initial', 10.00)")
    cursor.execute("SELECT MAX(product_id) FROM Products")
    max_id = cursor.fetchone()[0]
    print(f"Current max product_id: {max_id}")
    
    # Bulk copy with explicit identity values (keep_identity=True)
    data = [
        (100, 'Product A', Decimal('25.99')),
        (101, 'Product B', Decimal('35.99')),
        (102, 'Product C', Decimal('45.99')),
    ]
    
    result = cursor.bulkcopy(
        'Products',
        data,
        keep_identity=True  # Preserve explicit identity values
    )
    
    print(f"✓ Copied {result['rows_copied']} rows with explicit identity values")
    
    # Verify identity values were preserved
    cursor.execute("SELECT product_id, product_name FROM Products WHERE product_id >= 100")
    rows = cursor.fetchall()
    print(f"✓ Found {len(rows)} rows with IDs: {[row[0] for row in rows]}")
    
    cursor.close()
    connection.close()


def example_7_performance_options():
    """Example 7: Using performance optimization options."""
    print("\n" + "=" * 60)
    print("Example 7: Performance Optimization")
    print("=" * 60)
    
    set_backend('core')
    connection = connect("Server=localhost;Database=testdb;UID=sa;PWD=YourPassword")
    cursor = connection.cursor()
    
    # Create table
    cursor.execute("""
        IF OBJECT_ID('BulkData', 'U') IS NOT NULL DROP TABLE BulkData;
        CREATE TABLE BulkData (
            id INT,
            data VARCHAR(100)
        )
    """)
    
    # Generate test data
    data = [(i, f'Row_{i}') for i in range(1, 50001)]
    
    print("Testing with performance options...")
    result = cursor.bulkcopy(
        'BulkData',
        data,
        batch_size=10000,      # Larger batch for better throughput
        table_lock=True,       # Lock table to reduce overhead
        check_constraints=False,  # Skip constraint checks (default)
        fire_triggers=False    # Skip triggers (default)
    )
    
    print(f"✓ Copied {result['rows_copied']:,} rows in {result['elapsed_time']:.3f} seconds")
    print(f"✓ Throughput: {result['rows_per_second']:,.0f} rows/second")
    print(f"✓ Average batch time: {result['elapsed_time']/result['batch_count']:.3f} seconds")
    
    cursor.close()
    connection.close()


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "BULK COPY EXAMPLES - MSSQL-PYTHON" + " " * 14 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    print("These examples demonstrate the cursor.bulkcopy() method")
    print("for high-performance data loading with the Core TDS backend.")
    print()
    
    examples = [
        ("Simple Bulk Copy", example_1_simple_bulkcopy),
        ("Large Dataset", example_2_large_dataset),
        ("Generator", example_3_generator),
        ("Pandas DataFrame", example_4_pandas_dataframe),
        ("Column Mappings", example_5_column_mappings),
        ("Identity Columns", example_6_identity_columns),
        ("Performance Options", example_7_performance_options),
    ]
    
    for name, func in examples:
        try:
            func()
        except Exception as e:
            print(f"\n⚠ Example '{name}' failed: {e}")
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    main()
