"""
Simple test script to verify MT5 MCP server installation.
This script helps verify the server can be imported and basic functionality works.
"""

print("Testing MT5 MCP Server installation...\n")

# Test 1: Import the package
print("1. Testing package import...")
try:
    import mt5_mcp
    print("   ✓ Package imported successfully")
    print(f"   Version: {mt5_mcp.__version__}")
except Exception as e:
    print(f"   ✗ Failed to import package: {e}")
    exit(1)

# Test 2: Import submodules
print("\n2. Testing submodule imports...")
try:
    from mt5_mcp import connection, executor, server
    print("   ✓ All submodules imported successfully")
except Exception as e:
    print(f"   ✗ Failed to import submodules: {e}")
    exit(1)

# Test 3: Test MT5 connection (will fail if MT5 is not running, which is expected)
print("\n3. Testing MT5 connection...")
try:
    from mt5_mcp.connection import get_connection
    conn = get_connection()
    print("   ✓ MT5 connection initialized")
    print(f"   Connected: {conn.validate_connection()}")
    
    # Get safe namespace
    namespace = conn.get_safe_namespace()
    print(f"   ✓ Safe namespace created with {len(namespace)} objects")
    print(f"   Available: {', '.join(list(namespace.keys())[:5])}...")
    
except RuntimeError as e:
    print(f"   ⚠ MT5 connection failed (expected if MT5 terminal is not running):")
    print(f"     {e}")
except Exception as e:
    print(f"   ✗ Unexpected error: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Test executor formatting
print("\n4. Testing result formatting...")
try:
    from mt5_mcp.executor import format_result
    import pandas as pd
    
    # Test dict formatting
    test_dict = {"symbol": "EURUSD", "bid": 1.0850, "ask": 1.0852}
    result = format_result(test_dict)
    print("   ✓ Dict formatting works")
    
    # Test DataFrame formatting
    test_df = pd.DataFrame({"time": [1, 2, 3], "close": [1.08, 1.09, 1.10]})
    result = format_result(test_df)
    print("   ✓ DataFrame formatting works")
    
except Exception as e:
    print(f"   ✗ Formatting test failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("Installation test complete!")
print("="*60)
print("\nNext steps:")
print("1. Ensure MT5 terminal is running")
print("2. Enable algo trading in MT5 (Tools → Options → Expert Advisors)")
print("3. Configure Claude Desktop with the MCP server (see README.md)")
print("4. Test by running: python -m mt5_mcp --log-file test.log")
