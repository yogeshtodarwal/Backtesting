# stock_trading/sizer.py

import backtrader as bt

class MaxCashSizer(bt.Sizer):
    params = (
        ('max_cash', 30000),
    )

    def _getsizing(self, comminfo, cash, data, isbuy):
        if isbuy:
            available_cash = min(self.params.max_cash, cash)
            size = available_cash // data.close[0]
            print(f"Calculating size: available_cash = {available_cash}, data.close[0] = {data.close[0]}, size = {size}")
            return size
        return self.broker.getposition(data).size
