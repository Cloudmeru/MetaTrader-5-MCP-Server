# Chart File Management & Hyperlinks

## Overview

As of the latest update, MT5-MCP automatically saves all generated charts to the **current working directory** (where your terminal session is running) and provides **clickable file:// hyperlinks** in the output for easy access.

## How It Works

### 1. Chart Save Location

All charts are now saved to `os.getcwd()` (your current working directory):

```python
# Before: Charts saved to absolute path or project root
chart_path = Path("btcusd_chart.png").absolute()

# Now: Charts saved to current working directory
chart_path = _get_chart_save_path("btcusd_chart.png")
# Result: C:\Git\MT5-MCP\btcusd_chart.png (if running from C:\Git\MT5-MCP)
```

### 2. Clickable Hyperlinks

All chart paths are formatted as clickable Markdown hyperlinks:

```markdown
[btcusd_trend_forecast.png](file:///C:/Git/MT5-MCP/btcusd_trend_forecast.png)
```

**Features:**
- ✅ Clickable in VS Code
- ✅ Clickable in markdown viewers
- ✅ Handles spaces in filenames (URL-encoded)
- ✅ Works on Windows (converts backslashes to forward slashes)

### 3. MCP Response Format

When using the `mt5_analyze` tool, you'll see:

```json
{
  "chart_path": "C:\\Git\\MT5-MCP\\btcusd_trend_ml_forecast.png",
  "forecast_chart_path": "C:\\Git\\MT5-MCP\\forecast_BTCUSD_H1.png"
}
```

Followed by clickable links:

```
---
### 📁 Generated Files
📊 Chart: [btcusd_trend_ml_forecast.png](file:///C:/Git/MT5-MCP/btcusd_trend_ml_forecast.png)
🔮 Forecast: [forecast_BTCUSD_H1.png](file:///C:/Git/MT5-MCP/forecast_BTCUSD_H1.png)
---
```

## Examples

### Example 1: Running from Project Root

```powershell
cd C:\Git\MT5-MCP
# Run analysis via MCP tool
```

**Charts saved to:** `C:\Git\MT5-MCP\`

### Example 2: Running from Custom Directory

```powershell
cd C:\Users\YourName\Desktop\trading_analysis
# Run analysis via MCP tool
```

**Charts saved to:** `C:\Users\YourName\Desktop\trading_analysis\`

### Example 3: Using with Test Scripts

```python
import os
os.chdir("C:/analysis_output")

# Now run analysis
request = MT5AnalysisRequest(...)
response = handle_mt5_analysis(request)

# Charts will be in C:/analysis_output/
```

## Benefits

1. **Session Context Awareness**: Charts save where you're working, not a fixed location
2. **Easy Access**: Click hyperlinks directly in VS Code or terminal output
3. **Organized Workflow**: Keep charts with related analysis files
4. **Path Encoding**: Handles special characters and spaces automatically

## Technical Details

### Helper Functions

#### `_get_chart_save_path(filename: str) -> Path`

Resolves chart filename to absolute path in current working directory.

```python
cwd = os.getcwd()
return Path(cwd) / filename
```

#### `_format_file_hyperlink(file_path: str) -> str`

Formats file path as clickable Markdown hyperlink.

```python
abs_path = Path(file_path).absolute()
url_path = str(abs_path).replace('\\', '/')
encoded_path = quote(url_path, safe='/:')
filename = abs_path.name
return f"[{filename}](file:///{encoded_path})"
```

### Files Modified

- `src/mt5_mcp/handlers.py`: Chart generation functions
- `src/mt5_mcp/server.py`: Response formatter with hyperlinks

## Compatibility

- ✅ Windows (primary platform for MT5)
- ✅ VS Code (clickable file:// links)
- ✅ Markdown viewers
- ✅ Terminal output (copy-paste URLs)

## Migration from Previous Versions

**No action required!** The change is backward compatible:
- Charts still have the same filenames
- Paths are still returned in response
- Now just saved to your working directory instead of fixed location

## Troubleshooting

### Charts Not Found

If you can't find generated charts:

```powershell
# Check current directory
pwd

# Charts are saved here
ls *.png
```

### Hyperlinks Not Clickable

- **VS Code**: Ctrl+Click on the link
- **Terminal**: Copy-paste the URL into browser or file explorer
- **Claude Desktop**: Links may not be clickable in chat interface (use file path)

### Permission Errors

If you get permission errors saving charts:

```powershell
# Change to directory where you have write access
cd C:\Users\YourName\Documents
# Then run analysis
```

## Best Practices

1. **Start from Project Directory**: `cd C:\Git\MT5-MCP` before running analysis
2. **Use Dedicated Folders**: Create analysis output folders for organization
3. **Check Chart Names**: Files are auto-named by symbol and timeframe
4. **Clean Up Periodically**: Remove old chart files to avoid clutter

## Example Workflow

```powershell
# 1. Create analysis folder
mkdir C:\trading_analysis\2025-11-27
cd C:\trading_analysis\2025-11-27

# 2. Run MT5 analysis via MCP
# Charts will save to C:\trading_analysis\2025-11-27\

# 3. Click hyperlinks in output to view charts

# 4. Charts are organized with your analysis files
ls
# btcusd_trend_ml_forecast.png
# forecast_BTCUSD_H1.png
# ethusd_trend_ml_forecast.png
# forecast_ETHUSD_H1.png
```

## Related Features

- **XGBoost ML Signals**: See [XGBOOST_ML_SIGNAL.md](XGBOOST_ML_SIGNAL.md)
- **Prophet Forecasting**: See [FORECAST_EXAMPLES.md](FORECAST_EXAMPLES.md)
- **Analysis Tool**: See [QUICK_START_v0.4.0.md](QUICK_START_v0.4.0.md)

---

**Version**: MT5-MCP v0.4.0  
**Last Updated**: November 27, 2025
