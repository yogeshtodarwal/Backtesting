# stock_trading/strategy.py

import backtrader as bt

EMA_PERIOD = 5

class BuyAboveHigh(bt.Strategy):
    params = (
        ('ema_period', EMA_PERIOD),
    )

    def __init__(self):
        self.ema = {}
        self.buy_signal = {}
        self.buy_prices = {}
        self.sell_prices = {}
        self.stop_loss = {}
        self.target = {}
        self.trades = []

        for data in self.datas:
            self.ema[data._name] = bt.indicators.ExponentialMovingAverage(data.close, period=self.params.ema_period)
            self.buy_signal[data._name] = bt.indicators.CrossOver(data.close, self.ema[data._name])
            self.buy_prices[data._name] = []
            self.sell_prices[data._name] = []
            self.stop_loss[data._name] = None
            self.target[data._name] = None

    def next(self):
        for data in self.datas:
            if not self.getposition(data).size:
                if len(data) > self.params.ema_period and data.close[0] > data.high[-1] and data.high[-1] < self.ema[data._name][-1]:
                    stop_loss = 0.75 * data.close[0]
                    target = 3 * data.close[0]

                    size = self.broker.get_cash() // data.close[0]
                    size = min(size, 30000 // data.close[0])
                    if size > 0:
                        print(f"Buying {size} shares of {data._name} at {data.close[0]} for a total of {size * data.close[0]}")
                        self.buy(data=data, price=data.close[0], size=size)
                        self.buy_prices[data._name].append(data.close[0])
                        self.stop_loss[data._name] = stop_loss
                        self.target[data._name] = target
            else:
                if self.target[data._name] is not None and self.stop_loss[data._name] is not None:
                    if data.close[0] >= self.target[data._name] or data.close[0] <= self.stop_loss[data._name]:
                        print(f"Selling {self.getposition(data).size} shares of {data._name} at {data.close[0]}")
                        self.sell(data=data, price=data.close[0])
                        self.sell_prices[data._name].append(data.close[0])
                        self.stop_loss[data._name] = None
                        self.target[data._name] = None

    def notify_trade(self, trade):
        if trade.isclosed:
            data = trade.data
            ticker = data._name
            trade_info = {
                'ticker': ticker,
                'buy_price': int(round(self.buy_prices[ticker][-1])) if self.buy_prices[ticker] else None,
                'sell_price': int(round(self.sell_prices[ticker][-1])) if self.sell_prices[ticker] else None,
                'profit': int(round(trade.pnl))
            }
            self.trades.append(trade_info)
            print(f'Closed: {ticker}, Profit: {trade.pnl:.2f}, Buy Price: {self.buy_prices[ticker][-1]:.2f}, Sell Price: {self.sell_prices[ticker][-1]:.2f}')
