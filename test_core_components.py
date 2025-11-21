"""
Simple test for Core TDS backend components (without requiring built binaries).
"""

import sys
import os

# Add mssql_python to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mssql_python'))

def test_backend_config():
    """Test backend_config module"""
    print("Testing backend_config module...")
    
    from backend_config import set_backend, get_backend, reset_backend
    
    # Default should be ODBC
    backend = get_backend()
    print(f"  Default backend: {backend}")
    assert backend == 'odbc', f"Expected 'odbc', got '{backend}'"
    
    # Switch to Core
    set_backend('core')
    backend = get_backend()
    print(f"  After set_backend('core'): {backend}")
    assert backend == 'core', f"Expected 'core', got '{backend}'"
    
    # Test invalid backend
    try:
        set_backend('invalid')
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"  Correctly rejected invalid backend: {e}")
    
    # Reset to default
    reset_backend()
    backend = get_backend()
    print(f"  After reset_backend(): {backend}")
    assert backend == 'odbc', f"Expected 'odbc', got '{backend}'"
    
    # Test environment variable override
    os.environ['MSSQL_PYTHON_BACKEND'] = 'core'
    backend = get_backend()
    print(f"  With MSSQL_PYTHON_BACKEND=core: {backend}")
    assert backend == 'core', f"Expected 'core', got '{backend}'"
    del os.environ['MSSQL_PYTHON_BACKEND']
    
    print("✓ backend_config tests passed\n")


def test_client_context_builder():
    """Test ClientContextBuilder"""
    print("Testing ClientContextBuilder...")
    
    # Mock the _ConnectionStringParser since we can't import the full module
    import types
    import sys
    
    # Create a mock connection_string_parser module
    mock_parser_module = types.ModuleType('connection_string_parser')
    
    class MockConnectionStringParser:
        def __init__(self, validate_keywords=False):
            self.validate_keywords = validate_keywords
        
        def _parse(self, conn_str):
            """Simple parser that splits on semicolons"""
            result = {}
            if not conn_str:
                return result
            
            for pair in conn_str.split(';'):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    result[key.strip().lower()] = value.strip()
            return result
    
    mock_parser_module._ConnectionStringParser = MockConnectionStringParser
    sys.modules['connection_string_parser'] = mock_parser_module
    sys.modules['mssql_python.connection_string_parser'] = mock_parser_module
    
    # Now we can import ClientContextBuilder
    from client_context_builder import ClientContextBuilder
    
    conn_str = "Server=localhost;Database=testdb;UID=sa;PWD=password123;Encrypt=yes;TrustServerCertificate=true;PacketSize=8192;ConnectTimeout=30"
    
    ctx = ClientContextBuilder.build_from_connection_string(conn_str)
    
    print(f"  Connection string: {conn_str}")
    print(f"  Parsed ClientContext:")
    for key, value in sorted(ctx.items()):
        if key == 'password':
            print(f"    {key}: ***")
        else:
            print(f"    {key}: {value}")
    
    # Verify key mappings
    assert ctx['server'] == 'localhost', f"Expected server='localhost', got '{ctx['server']}'"
    assert ctx['database'] == 'testdb', f"Expected database='testdb', got '{ctx['database']}'"
    assert ctx['user_name'] == 'sa', f"Expected user_name='sa', got '{ctx['user_name']}'"
    assert ctx['password'] == 'password123'
    assert ctx['encryption'] == 'Mandatory', f"Expected encryption='Mandatory', got '{ctx['encryption']}'"
    assert ctx['trust_server_certificate'] == True
    assert ctx['packet_size'] == 8192
    assert ctx['connect_timeout'] == 30
    
    # Test defaults
    assert ctx['mars_enabled'] == False
    assert ctx['application_name'] == 'mssql-python'
    
    print("✓ ClientContextBuilder tests passed\n")


def test_backend_adapter():
    """Test BackendAdapter structure"""
    print("Testing BackendAdapter...")
    
    # Mock dependencies
    import types
    import sys
    
    mock_config = types.ModuleType('backend_config')
    mock_config.get_backend = lambda: 'odbc'
    sys.modules['backend_config'] = mock_config
    sys.modules['mssql_python.backend_config'] = mock_config
    
    mock_builder = types.ModuleType('client_context_builder')
    mock_builder.ClientContextBuilder = type('ClientContextBuilder', (), {
        'build_from_connection_string': staticmethod(lambda s: {'server': 'localhost'})
    })
    sys.modules['client_context_builder'] = mock_builder
    sys.modules['mssql_python.client_context_builder'] = mock_builder
    
    mock_bindings = types.ModuleType('ddbc_bindings')
    sys.modules['ddbc_bindings'] = mock_bindings
    sys.modules['mssql_python.ddbc_bindings'] = mock_bindings
    
    from backend_adapter import BackendAdapter, CORE_AVAILABLE
    
    print(f"  Core backend available: {CORE_AVAILABLE}")
    print(f"  BackendAdapter.create_connection method exists: {hasattr(BackendAdapter, 'create_connection')}")
    
    # Verify the class structure
    assert hasattr(BackendAdapter, 'create_connection'), "BackendAdapter should have create_connection method"
    
    print("✓ BackendAdapter structure validated\n")


def test_parameter_mappings():
    """Test parameter mapping coverage"""
    print("Testing parameter mappings...")
    
    import types
    import sys
    
    # Mock parser
    mock_parser_module = types.ModuleType('connection_string_parser')
    class MockParser:
        def __init__(self, validate_keywords=False):
            pass
        def _parse(self, s):
            result = {}
            for pair in s.split(';'):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    result[k.strip().lower()] = v.strip()
            return result
    mock_parser_module._ConnectionStringParser = MockParser
    sys.modules['connection_string_parser'] = mock_parser_module
    sys.modules['mssql_python.connection_string_parser'] = mock_parser_module
    
    from client_context_builder import ClientContextBuilder
    
    # Test various parameter synonyms
    test_cases = [
        ("Server=srv", 'server', 'srv'),
        ("Data Source=srv2", 'server', 'srv2'),
        ("Database=db1", 'database', 'db1'),
        ("Initial Catalog=db2", 'database', 'db2'),
        ("UID=user1", 'user_name', 'user1'),
        ("User ID=user2", 'user_name', 'user2'),
        ("PWD=pass1", 'password', 'pass1'),
        ("Password=pass2", 'password', 'pass2'),
        ("MARS=true", 'mars_enabled', True),
        ("MultipleActiveResultSets=yes", 'mars_enabled', True),
        ("Encrypt=no", 'encryption', 'Disabled'),
        ("Encrypt=yes", 'encryption', 'Mandatory'),
    ]
    
    for conn_str, expected_key, expected_value in test_cases:
        ctx = ClientContextBuilder.build_from_connection_string(conn_str)
        actual_value = ctx.get(expected_key)
        print(f"  {conn_str:35} → {expected_key}: {actual_value}")
        assert actual_value == expected_value, f"Expected {expected_key}={expected_value}, got {actual_value}"
    
    print("✓ Parameter mapping tests passed\n")


if __name__ == "__main__":
    print("=" * 70)
    print("Core TDS Backend Component Tests (Standalone)")
    print("=" * 70)
    print()
    
    try:
        test_backend_config()
        test_client_context_builder()
        test_backend_adapter()
        test_parameter_mappings()
        
        print("=" * 70)
        print("✓ All component tests passed!")
        print("=" * 70)
        print()
        print("Next steps:")
        print("  1. Build mssql-py-core: cd mssql-tds/mssql-py-core && maturin develop")
        print("  2. Build mssql-python ODBC bindings")
        print("  3. Test actual connections with Core backend")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
