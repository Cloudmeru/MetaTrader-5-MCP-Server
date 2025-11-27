import MetaTrader5 as mt5
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Initialize MT5
if not mt5.initialize():
    print("MT5 initialization failed")
    mt5.shutdown()
    exit()

# Get 30 days of daily data for ETHUSD
rates = mt5.copy_rates_from_pos('ETHUSD', mt5.TIMEFRAME_D1, 0, 30)

if rates is None or len(rates) == 0:
    print("Failed to retrieve ETHUSD data")
    mt5.shutdown()
    exit()

# Convert to DataFrame
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

# Calculate indicators
df['SMA_7'] = df['close'].rolling(7).mean()
df['SMA_20'] = df['close'].rolling(20).mean()

# Create chart
fig, ax = plt.subplots(figsize=(14, 7))

ax.plot(df['time'], df['close'], label='ETHUSD Close', linewidth=2, color='#2962FF')
ax.plot(df['time'], df['SMA_7'], label='SMA 7', linestyle='--', color='#FF6D00', alpha=0.8)
ax.plot(df['time'], df['SMA_20'], label='SMA 20', linestyle='--', color='#00C853', alpha=0.8)

ax.set_title('ETHUSD - Last 30 Days Trend', fontsize=16, fontweight='bold')
ax.set_xlabel('Date', fontsize=12)
ax.set_ylabel('Price (USD)', fontsize=12)
ax.legend(loc='best', fontsize=10)
ax.grid(True, alpha=0.3)

plt.xticks(rotation=45)
plt.tight_layout()

# Save chart
output_file = 'C:/Git/MT5-MCP/ethusd_trend.png'
plt.savefig(output_file, dpi=100, bbox_inches='tight')
print(f"📊 Chart saved to: {output_file}")

# Print summary
print(f"\n📈 ETHUSD Trend Summary (Last 30 Days)")
print(f"{'='*50}")
print(f"Period: {df['time'].iloc[0].strftime('%Y-%m-%d')} to {df['time'].iloc[-1].strftime('%Y-%m-%d')}")
print(f"Starting Price: ${df['close'].iloc[0]:.2f}")
print(f"Current Price: ${df['close'].iloc[-1]:.2f}")
print(f"Change: ${df['close'].iloc[-1] - df['close'].iloc[0]:.2f} ({((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100:.2f}%)")
print(f"Highest: ${df['high'].max():.2f}")
print(f"Lowest: ${df['low'].min():.2f}")
print(f"Average: ${df['close'].mean():.2f}")

mt5.shutdown()
