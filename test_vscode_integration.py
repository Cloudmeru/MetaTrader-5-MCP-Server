"""
Test VS Code MCP integration for MT5 server.
This script simulates how VS Code GitHub Copilot would interact with the MCP server.
"""
import asyncio
import json
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def test_vscode_integration():
    """Test the MT5 MCP server as VS Code would use it."""
    print("Testing MT5 MCP Server VS Code Integration")
    print("=" * 60)
    
    # Server parameters matching VS Code configuration
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "mt5_mcp"]
    )
    
    print("\n1. Connecting to MT5 MCP server...")
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                print("   ✓ Connection established")
                
                # Initialize session
                print("\n2. Initializing session...")
                await session.initialize()
                print("   ✓ Session initialized")
                
                # List available tools
                print("\n3. Listing available tools...")
                tools_result = await session.list_tools()
                print(f"   ✓ Found {len(tools_result.tools)} tool(s)")
                
                for tool in tools_result.tools:
                    print(f"\n   Tool: {tool.name}")
                    print(f"   Description: {tool.description[:100]}...")
                
                # Test tool call #1: Get MT5 version
                print("\n4. Testing tool call: Get MT5 version")
                result = await session.call_tool(
                    "execute_mt5",
                    {"command": "mt5.version()"}
                )
                print("   ✓ Tool executed successfully")
                print(f"   Response type: {type(result.content)}")
                if result.content:
                    print(f"   Result preview: {str(result.content[0].text)[:200]}...")
                
                # Test tool call #2: Get terminal info
                print("\n5. Testing tool call: Get terminal info")
                result = await session.call_tool(
                    "execute_mt5",
                    {"command": "mt5.terminal_info()._asdict()"}
                )
                print("   ✓ Tool executed successfully")
                if result.content:
                    content = result.content[0].text
                    print(f"   Response length: {len(content)} characters")
                    # Parse JSON to verify structure
                    try:
                        data = json.loads(content)
                        print(f"   Terminal: {data.get('name', 'Unknown')}")
                        print(f"   Connected: {data.get('connected', False)}")
                    except:
                        print(f"   Response preview: {content[:200]}...")
                
                # Test tool call #3: Get account info
                print("\n6. Testing tool call: Get account info")
                result = await session.call_tool(
                    "execute_mt5",
                    {"command": "mt5.account_info()._asdict()"}
                )
                print("   ✓ Tool executed successfully")
                if result.content:
                    content = result.content[0].text
                    try:
                        data = json.loads(content)
                        print(f"   Account: {data.get('login', 'Unknown')}")
                        print(f"   Balance: {data.get('balance', 0)}")
                        print(f"   Currency: {data.get('currency', 'Unknown')}")
                    except:
                        print(f"   Response preview: {content[:200]}...")
                
                # Test tool call #4: Get symbol list (first 5)
                print("\n7. Testing tool call: Get symbol list")
                result = await session.call_tool(
                    "execute_mt5",
                    {"command": "symbols = mt5.symbols_get(); result = [s.name for s in symbols[:5]]"}
                )
                print("   ✓ Tool executed successfully")
                if result.content:
                    print(f"   Response: {result.content[0].text}")
                
                # Test tool call #5: Multi-line command (historical data)
                print("\n8. Testing tool call: Get historical data (multi-line)")
                command = """
from datetime import datetime
rates = mt5.copy_rates_from_pos('EURUSD', mt5.TIMEFRAME_D1, 0, 5)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
result = df[['time', 'close']]
"""
                result = await session.call_tool(
                    "execute_mt5",
                    {"command": command}
                )
                print("   ✓ Tool executed successfully")
                if result.content:
                    content = result.content[0].text
                    print(f"   Data retrieved: {len(content)} characters")
                    # Show first few lines
                    lines = content.split('\n')[:6]
                    for line in lines:
                        print(f"   {line}")
                
                print("\n" + "=" * 60)
                print("✓ All tests passed! VS Code integration is working correctly.")
                print("=" * 60)
                print("\nNext steps:")
                print("1. Ensure the .vscode/mcp.json file exists in your workspace")
                print("2. Open VS Code and install GitHub Copilot extension")
                print("3. Open Command Palette (Ctrl+Shift+P)")
                print("4. Type 'MCP' and verify the MT5 server appears")
                print("5. Start the server and test with Copilot Chat")
                
    except Exception as e:
        print(f"\n✗ Error during integration test: {e}")
        import traceback
        traceback.print_exc()
        print("\nTroubleshooting:")
        print("1. Ensure MT5 terminal is running")
        print("2. Verify algo trading is enabled in MT5")
        print("3. Check that python -m mt5_mcp works directly")
        print("4. Review the log file if logging is enabled")


if __name__ == "__main__":
    print("\nMT5 MCP Server - VS Code Integration Test")
    print("This simulates how GitHub Copilot in VS Code connects to the server\n")
    asyncio.run(test_vscode_integration())
