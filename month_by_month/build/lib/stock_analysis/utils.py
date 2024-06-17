# stock_trading/utils.py

import pandas as pd

def save_trades_to_csv(trades, filename):
    trades.to_csv(filename, index=False)
    print(f"All trades report saved to {filename}")
