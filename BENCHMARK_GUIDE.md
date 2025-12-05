# Bulk Copy Performance Benchmarking Guide

This guide provides instructions for running bulk copy performance benchmarks to compare different optimization approaches.

## Overview

We have four benchmark scripts that test different scenarios:

1. **Small Strings (10 chars)**: Tests with typical small string data
   - `test_fastpath_benchmark.py` - Fast-path optimization
   - `test_raw_tds_benchmark.py` - Python TDS serialization

2. **Large Strings (1KB)**: Tests with realistic large string data
   - Same scripts, but with 1KB strings configured

3. **Wide Tables (1000 INT columns)**: Tests with many columns
   - `test_fastpath_wide_table.py` - Fast-path optimization
   - `test_raw_tds_wide_table.py` - Python TDS serialization

## Prerequisites

### Linux Setup

1. **SQL Server Instance**: Ensure SQL Server is running and accessible
   ```bash
   # SQL Server should be running on localhost:1433
   # Default credentials: sa / <password-from-file>
   ```

2. **Python Environment**: Python 3.10+ with required packages
   ```bash
   cd /path/to/mssql-python
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   pip install -r requirements.txt
   ```

3. **Build mssql-tds Library**:
   ```bash
   cd /path/to/mssql-tds
   cargo build --release
   ```

4. **Build mssql_core_tds Python Extension**:
   ```bash
   cd /path/to/mssql-tds/mssql-py-core
   maturin develop --release
   ```

5. **Install mssql_python Package**:
   ```bash
   cd /path/to/mssql-python
   pip install -e .
   ```

6. **Password File**: Create password file for SQL Server
   ```bash
   echo "YourStrongPassword" > /tmp/password
   ```

### Windows Setup

1. **SQL Server Instance**: Ensure SQL Server is running
   ```powershell
   # SQL Server should be running on localhost:1433
   # Or update SERVER variable in benchmark scripts
   ```

2. **Python Environment**: Python 3.10+ with required packages
   ```powershell
   cd C:\path\to\mssql-python
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. **Build mssql-tds Library**:
   ```powershell
   cd C:\path\to\mssql-tds
   cargo build --release
   ```

4. **Build mssql_core_tds Python Extension**:
   ```powershell
   cd C:\path\to\mssql-tds\mssql-py-core
   maturin develop --release
   ```

5. **Install mssql_python Package**:
   ```powershell
   cd C:\path\to\mssql-python
   pip install -e .
   ```

6. **Password File**: Create password file for SQL Server
   ```powershell
   # Option 1: Create in temp directory
   "YourStrongPassword" | Out-File -FilePath $env:TEMP\password -NoNewline
   
   # Option 2: Update benchmark scripts to read from Windows path
   # Edit each benchmark script and change:
   # PASSWORD = open("/tmp/password").read().strip()
   # to:
   # PASSWORD = open(r"C:\temp\password").read().strip()
   ```

## Configuration

Each benchmark script has configurable parameters at the top:

```python
# Connection details
SERVER = "localhost"
DATABASE = "master"
USER = "sa"
PASSWORD = open("/tmp/password").read().strip()  # Update path for Windows

# Test parameters
NUM_ROWS = 500_000      # Number of rows to insert
NUM_RUNS = 10           # Number of benchmark iterations
```

### Windows-Specific Configuration

For Windows, update the password file path in each benchmark script:

```python
# Change this (Linux):
PASSWORD = open("/tmp/password").read().strip()

# To this (Windows):
PASSWORD = open(r"C:\temp\password").read().strip()
# Or use environment variable:
PASSWORD = os.getenv("SQL_PASSWORD", "YourDefaultPassword")
```

## Running Benchmarks

### 1. Small Strings Benchmark (10 characters)

**Fast-Path Optimization:**
```bash
# Linux/Mac
cd /path/to/mssql-python
python test_fastpath_benchmark.py

# Windows
cd C:\path\to\mssql-python
python test_fastpath_benchmark.py
```

**Python TDS Serialization:**
```bash
# Linux/Mac
python test_raw_tds_benchmark.py

# Windows
python test_raw_tds_benchmark.py
```

**Expected Results (Small Strings):**
- Fast-path: ~391,000 rows/s (2.56µs per row)
- Python TDS: ~395,000 rows/s (2.53µs per row)
- Performance: Essentially identical

### 2. Large Strings Benchmark (1KB)

Both benchmark scripts are already configured for 1KB strings:
```python
large_string = "X" * 1024  # 1KB string
```

Run the same commands as above.

**Expected Results (1KB Strings):**
- Fast-path: ~33,000 rows/s (30µs per row)
- Python TDS: ~33,000 rows/s (31µs per row)
- Performance: Essentially identical
- Network I/O dominates (24-30µs)

### 3. Wide Table Benchmark (1000 INT columns)

**Fast-Path Optimization:**
```bash
# Linux/Mac
python test_fastpath_wide_table.py

# Windows
python test_fastpath_wide_table.py
```

**Python TDS Serialization:**
```bash
# Linux/Mac
python test_raw_tds_wide_table.py

# Windows
python test_raw_tds_wide_table.py
```

**Expected Results (1000 Columns):**
- Fast-path: ~6,486 rows/s (155µs per row)
  - Type conversion: 34µs
  - GIL overhead: ~30µs (19% of time)
  - TDS write: 85µs
- Python TDS: ~6,420 rows/s (156µs per row)
  - GIL overhead: 1.2µs (0.8% of time) - **96% lower!**
  - Write time: 150µs
- Performance: Essentially identical despite GIL differences

## Understanding the Results

### Profiling Output

Each benchmark prints profiling data every 10,000 rows:

**Fast-Path:**
```
[PROFILE] 100000 rows: avg GIL+conversion=5.103µs, avg type_conversion=4.766µs
[PROFILE] 100000 rows: avg TDS_write=30.312µs
```
- `GIL+conversion`: Total time holding GIL + type conversion
- `type_conversion`: Time spent converting Python types to Rust
- `TDS_write`: Time spent writing to SQL Server

**Python TDS Serialization:**
```
[PROFILE RAW] 100000 rows: avg GIL=594ns, avg write=29.703µs
```
- `GIL`: Time holding GIL for write operation
- `write`: Total write time including network I/O

### Summary Statistics

After 10 runs, you'll see:
```
======================================================================
RESULTS (10 successful runs):
======================================================================

Throughput (rows/s):
  Average:        32,983
  Median:         32,924
  Min:            31,324
  Max:            35,098
  Std Dev:         1,019

Time per row (µs):
  Average:         30.34
  Median:          30.37
  Min:             28.49
  Max:             31.92
  Std Dev:          0.93
```

## Troubleshooting

### Common Issues

1. **Connection Failures**
   ```
   Error: Cannot connect to SQL Server
   ```
   - Verify SQL Server is running
   - Check SERVER, USER, PASSWORD settings
   - Ensure port 1433 is accessible

2. **Module Not Found**
   ```
   ModuleNotFoundError: No module named 'mssql_core_tds'
   ```
   - Rebuild mssql_core_tds: `cd mssql-tds/mssql-py-core && maturin develop --release`
   - Activate virtual environment

3. **Table Already Exists**
   ```
   Error: There is already an object named 'benchmark_*' in the database
   ```
   - Drop the table manually: `DROP TABLE benchmark_*`
   - Or restart the benchmark (it should auto-cleanup)

4. **NVARCHAR Size Error** (Historical issue - now fixed)
   ```
   Error: The size (4096) given to the parameter 'name' exceeds the maximum allowed (4000)
   ```
   - This was fixed by correcting NVARCHAR metadata (byte count → character count)
   - If you see this, ensure you have the latest mssql-tds build

5. **Windows Path Issues**
   - Update password file path to Windows format
   - Use raw strings: `r"C:\path\to\file"`
   - Or use environment variables

### Performance Variations

Benchmark results may vary based on:
- **System Load**: CPU/memory usage affects measurements
- **Network Latency**: SQL Server connection speed (use localhost for best results)
- **SQL Server Configuration**: Buffer pool, memory settings
- **Disk I/O**: Database file location (SSD vs HDD)

For consistent results:
- Run on idle system
- Use localhost SQL Server
- Run multiple iterations (10+)
- Compare relative performance, not absolute numbers

## Benchmark Scenarios Summary

| Scenario | Data Size | Bottleneck | Winner | Key Insight |
|----------|-----------|------------|--------|-------------|
| Small strings (10 chars) | ~40 bytes/row | CPU encoding | Tied | GIL differences minimal |
| Large strings (1KB) | ~4KB/row | Network I/O | Tied | I/O dominates everything |
| Wide table (1000 INTs) | 4KB/row | Network I/O | Tied | 96% lower GIL but same throughput |

**Conclusion**: Both approaches (fast-path and Python serialization) deliver identical performance across all scenarios, with Python having lower GIL overhead but similar total execution time due to network I/O bottlenecks.

## Advanced Testing

### Custom Row Counts

Edit the benchmark scripts to test with different data volumes:

```python
NUM_ROWS = 1_000_000  # 1 million rows
NUM_RUNS = 5          # Fewer runs for large datasets
```

### Different Column Types

Modify the test data to include various SQL types:

```python
# Example: Mixed types
cursor.execute(f"""
    CREATE TABLE {TABLE_NAME} (
        id INT,
        name NVARCHAR(100),
        created DATETIME2,
        balance DECIMAL(18,2),
        is_active BIT
    )
""")
```

### Connection Pooling

Test with connection pooling enabled/disabled:

```python
# Add to connection string
conn_str = f"Server={SERVER};Database={DATABASE};UID={USER};PWD={PASSWORD};Pooling=true;Max Pool Size=100"
```

## Additional Resources

- [Rust mssql-tds Library](../mssql-tds/README.md)
- [Python Driver Documentation](./README.md)
- [TDS Protocol Specification](https://docs.microsoft.com/en-us/openspecs/windows_protocols/ms-tds/)
- [SQL Server Bulk Copy Protocol](https://docs.microsoft.com/en-us/sql/relational-databases/import-export/bulk-copy-operations-in-sql-server)

## Contributing

To add new benchmarks:

1. Copy an existing benchmark script
2. Modify the test data and schema
3. Update this guide with the new scenario
4. Document expected results and key insights
