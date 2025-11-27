import traceback
import MetaTrader5 as mt5

# Initialize MT5 like the server does
if not mt5.initialize():
    print("Failed to initialize MT5")
    exit(1)

from mt5_mcp.models import *
from mt5_mcp.handlers import handle_mt5_analysis

req = MT5AnalysisRequest(
    query=MT5QueryRequest(
        operation='copy_rates_from_pos',
        symbol='ETHUSD',
        parameters={'timeframe': 'D1', 'count': 30, 'start_pos': 0}
    ),
    indicators=[IndicatorSpec(function='ta.momentum.rsi', params={'window': 14})],
    chart=None,
    output_format='json',
    tail=5
)

try:
    result = handle_mt5_analysis(req)
    print("SUCCESS!")
    print(result)
except Exception as e:
    traceback.print_exc()
