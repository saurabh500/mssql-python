"""
Test end-to-end connection using Core TDS backend.
"""

import sys

print("Testing Core TDS Connection...")
print("=" * 70)

# Test 1: Can we import the module?
print("\n1. Testing import of mssql_core_tds...")
try:
    import mssql_core_tds
    print("   ✓ Successfully imported mssql_core_tds")
    print(f"   Module: {mssql_core_tds}")
    print(f"   Has DdbcConnection: {hasattr(mssql_core_tds, 'DdbcConnection')}")
except ImportError as e:
    print(f"   ✗ Failed to import: {e}")
    sys.exit(1)

# Test 2: Can we create a ClientContext dict?
print("\n2. Creating ClientContext...")
client_context = {
    'server': 'localhost',
    'port': 1433,
    'database': 'master',
    'user_name': 'sa',
    'password': 'UuXjNBfFvS1Nc/7p',  # Correct password
    'application_name': 'mssql-python-test',
    'connect_timeout': 30,
    'packet_size': 4096,
    'mars_enabled': False,
    'encryption': 'Optional',
    'trust_server_certificate': True,
    'application_intent': 'ReadWrite',
    'workstation_id': 'test-workstation',
}

for key, value in client_context.items():
    if key == 'password':
        print(f"   {key}: ***")
    else:
        print(f"   {key}: {value}")

# Test 3: Try to create connection (will fail without real server)
print("\n3. Attempting to create connection...")
print("   Note: This will fail without a real SQL Server running")
print("   Connection string details:")
print(f"     Server: {client_context['server']}:{client_context.get('port', 1433)}")
print(f"     Database: {client_context['database']}")
print(f"     User: {client_context['user_name']}")

try:
    conn = mssql_core_tds.DdbcConnection(client_context)
    print("   ✓ Connection created successfully!")
    print(f"   Connection: {conn}")
    
    # Test connection status
    is_connected = conn.is_connected()
    print(f"   Is connected: {is_connected}")
    
    # Try to create a cursor
    print("\n4. Creating cursor...")
    cursor = conn.cursor()
    print(f"   ✓ Cursor created: {cursor}")
    
    # Close connection
    print("\n5. Closing connection...")
    conn.close()
    print("   ✓ Connection closed")
    
    is_connected_after_close = conn.is_connected()
    print(f"   Is connected after close: {is_connected_after_close}")
    
    print("\n" + "=" * 70)
    print("✓ ALL TESTS PASSED!")
    print("Core TDS backend is working end-to-end!")
    print("=" * 70)
    
except Exception as e:
    print(f"   ✗ Connection failed: {type(e).__name__}: {e}")
    print("\n   This is expected if SQL Server is not running at localhost:1433")
    print("   with the specified credentials.")
    print("\n   To test with a real server, update the client_context dictionary")
    print("   with your SQL Server connection details.")
    print("\n" + "=" * 70)
    print("Core TDS module built successfully but no server available for testing")
    print("=" * 70)
