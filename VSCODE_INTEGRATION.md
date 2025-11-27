# MT5 MCP Server - VS Code Integration Guide

## Overview

This guide shows you how to integrate the MT5 MCP Server with Visual Studio Code's GitHub Copilot to enable AI-powered market data analysis directly in your development environment.

## Prerequisites

1. **Visual Studio Code** - Latest version installed
2. **GitHub Copilot Extension** - Installed and signed in
   - [Get GitHub Copilot](https://marketplace.visualstudio.com/items?itemName=GitHub.copilot)
3. **MetaTrader 5** - Running with algo trading enabled
4. **MT5 MCP Server** - Installed (see main README.md)
5. **Python 3.10+** - With the server installed

## Quick Setup

### Option 1: Automatic Configuration (Recommended)

1. Open VS Code Command Palette (`Ctrl+Shift+P`)
2. Type **"MCP: Add Server"** and press Enter
3. Select **"stdio"** as the transport type
4. Enter the following configuration:
   - **Server Name**: `mt5`
   - **Command**: `python`
   - **Args**: `-m mt5_mcp`

### Option 2: Manual Configuration

1. Open VS Code Command Palette (`Ctrl+Shift+P`)
2. Type **"MCP: Open User Configuration"** and press Enter
3. This opens the `mcp.json` file in `.vscode` folder
4. Add the MT5 server configuration:

```json
{
  "servers": {
    "mt5": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "mt5_mcp"]
    }
  }
}
```

### With Logging (for troubleshooting):

```json
{
  "servers": {
    "mt5": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "mt5_mcp", "--log-file", "C:\\logs\\mt5_mcp_vscode.log"]
    }
  }
}
```

## Configuration File Locations

VS Code uses different configuration files depending on the scope:

### User-Level Configuration
**Location**: `%USERPROFILE%\.vscode\mcp.json`

Applied to all VS Code sessions. Useful when you work with MT5 data regularly across projects.

### Workspace-Level Configuration
**Location**: `{workspace}\.vscode\mcp.json`

Applied only to specific workspace/project. Useful when only specific projects need MT5 access.

### Settings.json Alternative

You can also configure MCP servers in VS Code settings:

**File**: `settings.json` (User or Workspace)

```json
{
  "github.copilot.chat.mcpServers": {
    "mt5": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "mt5_mcp"]
    }
  }
}
```

## Starting the MCP Server

After configuration, you need to start the server:

1. Open GitHub Copilot Chat (`Ctrl+Alt+I`)
2. Click the **Tools** icon (🔧) in the chat toolbar
3. Find **"mt5"** in the list of available servers
4. Click **"Start"** button next to the server name

Alternatively, the server may auto-start when you use Agent Mode.

## Using the MT5 MCP Server in VS Code

### 1. Enable Agent Mode

Press `Ctrl+Alt+I` to open GitHub Copilot Chat, then:
- Click the agent mode toggle or
- Select an agent like Claude Sonnet 4

### 2. Grant Tool Access

When you first use the MT5 tools, GitHub Copilot will ask for permission:
- Review the tool capabilities
- Click **"Allow"** to grant access

You can manage tool permissions later in:
**Tools → Options → GitHub → Copilot → Tools**

### 3. Natural Language Queries

Ask questions in natural language:

**Example Queries:**

```
Get EURUSD symbol information

Show me last week's BTCUSD daily data

What symbols are available in my MT5 account?

Calculate the volatility of GBPUSD over the last 30 days

Get hourly data for USDJPY from the last 24 hours and show as table

What's my MT5 account balance?

Analyze the trend of EURUSD over the past month
```

### 4. Code Generation with MT5 Context

Copilot can generate code that uses MT5 data:

**Example:**
```
Create a Python script that fetches EURUSD daily data for the last 30 days 
and calculates moving averages
```

Copilot will generate code using the MT5 MCP server context.

## Verification Steps

### 1. Check Server Status

In GitHub Copilot Chat:
1. Click the Tools icon (🔧)
2. Verify "mt5" appears in the list
3. Status should show "Running" or with a Start button

### 2. Test Connection

Run this query in Copilot Chat:
```
Use the MT5 tool to get terminal information
```

Expected response: JSON with MT5 terminal details

### 3. Test Data Retrieval

```
Get last 5 days of EURUSD daily price data using MT5
```

Expected response: Table with OHLC data

## Troubleshooting

### Server Not Appearing in Tools List

**Issue**: MT5 server doesn't show up in Copilot tools

**Solutions**:
1. Restart VS Code after adding configuration
2. Verify `mcp.json` syntax (no trailing commas, proper quotes)
3. Check file location (user vs workspace)
4. Reload window: `Ctrl+Shift+P` → "Developer: Reload Window"

### Server Fails to Start

**Issue**: "Failed to start server" error

**Solutions**:
1. Verify MT5 terminal is running
2. Check Python is in PATH: `python --version`
3. Verify server installation: `python -m mt5_mcp --help`
4. Enable logging and check logs:
   ```json
   "args": ["-m", "mt5_mcp", "--log-file", "C:\\logs\\mt5_debug.log"]
   ```
5. Ensure algo trading is enabled in MT5

### Connection Errors

**Issue**: "MT5 connection error" in responses

**Solutions**:
1. Verify MT5 terminal is running
2. Enable algo trading: Tools → Options → Expert Advisors → "Allow automated trading"
3. Restart MT5 terminal
4. Check Windows Firewall isn't blocking Python

### No Data Returned

**Issue**: Queries return "No data" or empty results

**Solutions**:
1. Verify symbol name (case-sensitive: `EURUSD` not `eurusd`)
2. Check symbol availability: "List available symbols"
3. Verify date range is valid
4. Some symbols may have limited historical data

## Advanced Configuration

### Multiple Python Environments

If you have multiple Python installations:

```json
{
  "servers": {
    "mt5": {
      "type": "stdio",
      "command": "C:\\Python310\\python.exe",
      "args": ["-m", "mt5_mcp"]
    }
  }
}
```

### Virtual Environment

Using a specific virtual environment:

```json
{
  "servers": {
    "mt5": {
      "type": "stdio",
      "command": "C:\\projects\\mt5-env\\Scripts\\python.exe",
      "args": ["-m", "mt5_mcp"]
    }
  }
}
```

### Environment Variables

Pass environment variables to the server:

```json
{
  "servers": {
    "mt5": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "mt5_mcp"],
      "env": {
        "MT5_DATA_PATH": "C:\\custom\\path"
      }
    }
  }
}
```

## Example Workflows

### 1. Market Analysis Workflow

```
1. "Get EURUSD data for the last 30 days"
2. "Calculate the 20-day moving average"
3. "Plot the price with moving average" (generates matplotlib code)
4. "Identify support and resistance levels"
```

### 2. Multi-Symbol Comparison

```
1. "Get last week data for EURUSD, GBPUSD, and USDJPY"
2. "Calculate returns for each"
3. "Create a correlation matrix"
4. "Generate a comparison report"
```

### 3. Code Generation with MT5 Data

```
1. "Create a Python script that monitors BTCUSD volatility"
2. "Add error handling for MT5 connection"
3. "Save results to CSV file"
```

## Managing Tool Permissions

### View Current Permissions

1. Open Command Palette (`Ctrl+Shift+P`)
2. Type "GitHub Copilot: Manage Tool Permissions"
3. View/modify permissions for MT5 server

### Reset Tool Approvals

**Tools → Options → GitHub → Copilot → Tools → Reset Tool Confirmations**

This clears all saved tool permissions, requiring re-approval.

### Automatic Approval

To skip permission prompts (not recommended for security):

```json
{
  "github.copilot.chat.autoApproveTools": true
}
```

## Integration with VS Code Features

### Code Actions

Copilot can suggest MT5-related code actions:
- Right-click in code → "Copilot" → "Generate using MT5 data"

### IntelliSense

When writing MT5-related code, Copilot provides:
- Function signatures from MT5 module
- Common patterns for data retrieval
- Error handling suggestions

### Debugging Support

Use MT5 data during debugging:
1. Set breakpoints
2. In Debug Console, ask Copilot: "Get current EURUSD price"
3. Use data for conditional debugging

## Best Practices

### 1. Specific Queries

❌ Bad: "Get data"
✅ Good: "Get last 7 days of EURUSD daily data"

### 2. Error Context

Include error messages in follow-up queries:
```
The previous query failed with "Symbol not found". 
List available symbols starting with EUR.
```

### 3. Iterative Refinement

Start simple, then refine:
```
1. "Get EURUSD data"
2. "Format as table"
3. "Add calculated columns for returns"
4. "Export to CSV"
```

### 4. Context Awareness

Reference previous results:
```
1. "Get BTCUSD last week data"
2. "Calculate volatility from that data"
3. "Compare to previous month's volatility"
```

## Security Considerations

### Read-Only Access

The MT5 MCP server is **read-only** by design:
- ✅ Can query market data
- ✅ Can check account info
- ❌ Cannot place trades
- ❌ Cannot modify positions
- ❌ Cannot change settings

### Data Privacy

- Server runs locally (no data sent to external servers)
- Stdio transport (secure local communication)
- No network exposure by default

### Tool Approval

Always review tool permissions before approving:
- Understand what data the tool accesses
- Verify the command being executed
- Check for sensitive information in responses

## Common Use Cases

### 1. Research & Analysis

```
"Analyze EURUSD price action over the last quarter"
"Find correlations between EUR and GBP pairs"
"Calculate Sharpe ratio for BTCUSD"
```

### 2. Strategy Development

```
"Generate code for a simple moving average crossover strategy"
"Backtest this strategy using last year's data"
"Calculate maximum drawdown"
```

### 3. Automated Reporting

```
"Create a daily summary report for my watchlist"
"Generate a volatility report for all major pairs"
"Export account statistics to Excel"
```

### 4. Learning & Exploration

```
"Explain the MT5 symbol_info structure"
"Show me different ways to fetch historical data"
"What timeframes are available?"
```

## Comparison: VS Code vs Claude Desktop

| Feature | VS Code | Claude Desktop |
|---------|---------|----------------|
| **Integration** | GitHub Copilot | Standalone app |
| **Context** | Code-aware | Conversation-focused |
| **Editing** | Direct code generation | Copy/paste needed |
| **Debug** | Integrated debugger | No debugging |
| **Tools** | Multiple MCP servers | Multiple MCP servers |
| **Workflow** | Development-focused | Analysis-focused |

**Use VS Code when:**
- Developing trading scripts
- Integrating MT5 into applications
- Need code completion/generation
- Debugging MT5-based code

**Use Claude Desktop when:**
- Pure market analysis
- Quick data queries
- No coding required
- Conversational exploration

## Updating the Server

After updating the MT5 MCP server:

1. Stop the server in VS Code (Tools menu)
2. Update the package: `pip install -e . --upgrade`
3. Restart VS Code or reload window
4. Start the server again

## Performance Tips

### 1. Limit Data Ranges

Request only necessary data:
```
# Slow
"Get all EURUSD historical data"

# Fast
"Get last 30 days of EURUSD data"
```

### 2. Use Appropriate Timeframes

```
# For trend analysis
"Get daily data for last 3 months"

# For intraday analysis
"Get 1-hour data for last week"
```

### 3. Cache Results

Store frequently used data:
```python
# Generated by Copilot
rates = mt5.copy_rates_from_pos('EURUSD', mt5.TIMEFRAME_D1, 0, 30)
df = pd.DataFrame(rates)
df.to_csv('eurusd_cache.csv')  # Reuse later
```

## Next Steps

1. ✅ Complete the quick setup
2. ✅ Verify server is running
3. ✅ Test with simple queries
4. ✅ Explore natural language queries
5. ✅ Generate MT5-integrated code
6. ✅ Build custom analysis scripts

## Resources

- **VS Code MCP Documentation**: [Use MCP Servers](https://code.visualstudio.com/docs/copilot/chat/mcp-servers)
- **GitHub Copilot Docs**: [GitHub Copilot Extension](https://code.visualstudio.com/docs/copilot/overview)
- **MT5 MCP Server**: See main README.md
- **Quick Reference**: See QUICK_REFERENCE.md

## Support

### Common Commands

**List available symbols:**
```
What symbols are available?
```

**Check server status:**
```
Is the MT5 server connected?
```

**Get help:**
```
What can I do with the MT5 MCP server?
```

### Getting Help

1. Enable logging in configuration
2. Check log files for errors
3. Verify MT5 connection
4. Test with simple queries first
5. Review troubleshooting section

---

## Quick Reference Card

**Open Copilot Chat**: `Ctrl+Alt+I`
**Command Palette**: `Ctrl+Shift+P`
**Open MCP Config**: Command Palette → "MCP: Open User Configuration"
**Start Server**: Tools icon → Find "mt5" → Click "Start"
**View Tools**: Click 🔧 icon in Copilot Chat

**Test Query**: "Get EURUSD symbol information"

---

*Ready to supercharge your MT5 development with AI? Start asking questions in GitHub Copilot Chat!*
