import backtrader as bt
import yfinance as yf
import pandas as pd
from datetime import datetime
import calendar

EMA_PERIOD = 5
TOP_N = 5

class BuyAboveHigh(bt.Strategy):
    params = (('ema_period', EMA_PERIOD),)

    def __init__(self):
        self.ema = {data._name: bt.indicators.ExponentialMovingAverage(data.close, period=self.params.ema_period) for data in self.datas}
        self.buy_signal = {data._name: bt.indicators.CrossOver(data.close, self.ema[data._name]) for data in self.datas}
        self.buy_prices = {data._name: [] for data in self.datas}
        self.sell_prices = {data._name: [] for data in self.datas}
        self.stop_loss = {data._name: None for data in self.datas}
        self.target = {data._name: None for data in self.datas}
        self.trades = []

    def next(self):
        for data in self.datas:
            if not self.getposition(data).size:
                if len(data) > self.params.ema_period and data.close[0] > data.high[-1] and data.high[-1] < self.ema[data._name][-1]:
                    stop_loss = 0.75 * data.close[0]
                    target = 3 * data.close[0]
                    size = min(self.broker.get_cash() // data.close[0], 30000 // data.close[0])
                    if size > 0:
                        self.buy(data=data, price=data.close[0], size=size)
                        self.buy_prices[data._name].append(data.close[0])
                        self.stop_loss[data._name] = stop_loss
                        self.target[data._name] = target
            else:
                if self.target[data._name] is not None and self.stop_loss[data._name] is not None:
                    if data.close[0] >= self.target[data._name] or data.close[0] <= self.stop_loss[data._name]:
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
                'profit': int(round(trade.pnl)),
                'date': self.data.datetime.date(0).isoformat(),
                'cash': int(round(self.broker.get_cash())),
                'equity': int(round(self.broker.get_value()))
            }
            self.trades.append(trade_info)

class MaxCashSizer(bt.Sizer):
    params = (('max_cash', 30000),)

    def _getsizing(self, comminfo, cash, data, isbuy):
        if isbuy:
            available_cash = min(self.params.max_cash, cash)
            return available_cash // data.close[0]
        return self.broker.getposition(data).size

def fetch_data(ticker, start_date, end_date):
    data = yf.download(ticker, start=start_date, end=end_date, interval='1d')
    all_dates = pd.date_range(start=start_date, end=end_date, freq='B')
    data = data.reindex(all_dates, fill_value=0)
    return data

class TradingPipeline:
    def __init__(self, start_date, end_date, equity_file):
        self.start_date = start_date
        self.end_date = end_date
        self.stocks = pd.read_csv(equity_file)['Ticker'].tolist()
        self.all_data = self.fetch_all_data()
        self.cerebro = bt.Cerebro()
        self.cerebro.broker.set_cash(100000)
        self.cerebro.addsizer(MaxCashSizer)

    def fetch_all_data(self):
        return {ticker: fetch_data(f'{ticker}.NS', self.start_date, self.end_date) for ticker in self.stocks if not fetch_data(f'{ticker}.NS', self.start_date, self.end_date).empty and len(fetch_data(f'{ticker}.NS', self.start_date, self.end_date)) >= EMA_PERIOD}

    def process_month(self, date):
        month_end = date + pd.DateOffset(days=calendar.monthrange(date.year, date.month)[1] - 1)
        if month_end > datetime.now():
            return

        selected_stocks = []
        for ticker, df in self.all_data.items():
            if date in df.index and len(df.loc[:date]) > EMA_PERIOD:
                df_slice = df.loc[:date]
                last_row = df_slice.iloc[-1]
                prev_row = df_slice.iloc[-2]
                ema_value = df_slice['Close'].ewm(span=EMA_PERIOD, adjust=False).mean().iloc[-2]
                if last_row['Close'] > prev_row['High'] and prev_row['High'] < ema_value:
                    selected_stocks.append((ticker, last_row['Volume'], last_row['Close']))

        top_stocks = sorted(selected_stocks, key=lambda x: x[1], reverse=True)[:TOP_N]
        for ticker, _, _ in top_stocks:
            data = bt.feeds.PandasData(dataname=self.all_data[ticker], name=ticker)
            self.cerebro.adddata(data)

    def run(self):
        for date in pd.date_range(start=self.start_date, end=self.end_date, freq='MS'):
            self.process_month(date)

        self.cerebro.addstrategy(BuyAboveHigh)
        self.cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade')
        result = self.cerebro.run()
        strategy = result[0]
        trades = pd.DataFrame(strategy.trades)
        trades.to_csv('all_trades_report.csv', index=False)

def main():
    start_date = '2007-01-01'
    end_date = '2024-06-14'
    equity_file = 'equity_full.csv'
    pipeline = TradingPipeline(start_date, end_date, equity_file)
    pipeline.run()

if __name__ == '__main__':
    main()
