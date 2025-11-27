"""
Test the executor with sample MT5 commands.
"""

from mt5_mcp.connection import get_safe_namespace
from mt5_mcp.executor import execute_command

print("Testing MT5 command execution...\n")
print("="*60)

# Test 1: Get MT5 version
print("\n1. Testing: Get MT5 version")
print("-" * 60)
namespace = get_safe_namespace()
result = execute_command("mt5.version()", namespace)
print(result)

# Test 2: Get terminal info
print("\n2. Testing: Get terminal info")
print("-" * 60)
namespace = get_safe_namespace()
result = execute_command("mt5.terminal_info()._asdict()", namespace)
print(result)

# Test 3: Get account info
print("\n3. Testing: Get account info")
print("-" * 60)
namespace = get_safe_namespace()
result = execute_command("mt5.account_info()._asdict()", namespace)
print(result)

# Test 4: Get available symbols (first 5)
print("\n4. Testing: Get first 5 symbols")
print("-" * 60)
namespace = get_safe_namespace()
result = execute_command("symbols = mt5.symbols_get(); [s.name for s in symbols[:5]]", namespace)
print(result)

# Test 5: Get symbol info for EURUSD
print("\n5. Testing: Get EURUSD symbol info")
print("-" * 60)
namespace = get_safe_namespace()
result = execute_command("mt5.symbol_info('EURUSD')._asdict()", namespace)
print(result)

# Test 6: Multi-line command - get last 7 days of data
print("\n6. Testing: Get last 7 days EURUSD data")
print("-" * 60)
namespace = get_safe_namespace()
command = """
from datetime import datetime
rates = mt5.copy_rates_from_pos('EURUSD', mt5.TIMEFRAME_D1, 0, 7)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
result = df[['time', 'open', 'high', 'low', 'close']]
"""
result = execute_command(command, namespace)
print(result)

print("\n" + "="*60)
print("All tests completed!")
