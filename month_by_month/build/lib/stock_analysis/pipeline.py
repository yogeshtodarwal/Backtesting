# stock_trading/pipeline.py

import pandas as pd
import backtrader as bt
from datetime import datetime
import calendar

from .data_fetcher import fetch_data
from .strategy import BuyAboveHigh
from .sizer import MaxCashSizer

class TradingPipeline:
    def __init__(self, start_date, end_date, equity_file):
        self.start_date = start_date
        self.end_date = end_date
        self.equity_file = equity_file
        self.stocks = pd.read_csv(equity_file)['Ticker'].tolist()
        self.all_data = self.fetch_all_data()
        self.cerebro = bt.Cerebro()
        self.cerebro.broker.set_cash(100000)
        self.cerebro.addsizer(MaxCashSizer)

    def fetch_all_data(self):
        all_data = {}
        for ticker in self.stocks:
            print(f'Fetching data for {ticker}...')
            df = fetch_data(f'{ticker}.NS', self.start_date, self.end_date)
            if not df.empty and len(df) >= EMA_PERIOD:
                all_data[ticker] = df
            else:
                print(f"No sufficient data for {ticker}. Skipping.")
        return all_data

    def process_month(self, date):
        month_end = date + pd.DateOffset(days=calendar.monthrange(date.year, date.month)[1] - 1)
        if month_end > datetime.now():
            return

        print(f'Processing month: {date.strftime("%Y-%m")}')

        selected_stocks = []
        for ticker, df in self.all_data.items():
            if date in df.index and len(df.loc[:date]) > EMA_PERIOD:
                df_slice = df.loc[:date]
                last_row = df_slice.iloc[-1]
                prev_row = df_slice.iloc[-2]
                ema_value = df_slice['Close'].ewm(span=EMA_PERIOD, adjust=False).mean().iloc[-2]

                if last_row['Close'] > prev_row['High'] and prev_row['High'] < ema_value:
                    selected_stocks.append((ticker, last_row['Volume'], last_row['Close']))

        selected_stocks.sort(key=lambda x: x[1], reverse=True)
        top_stocks = selected_stocks[:TOP_N]

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
        trade_analysis = strategy.analyzers.trade.get_analysis()

        all_trades_data = {
            'Ticker': [],
            'Total Trades': [],
            'Profitable Trades': [],
            'Losing Trades': [],
            'Total Profit/Loss': [],
            'Buy Prices': [],
            'Sell Prices': [],
            'Month': []
        }

        for trade in strategy.trades:
            ticker = trade['ticker']
            all_trades_data['Ticker'].append(ticker)
            all_trades_data['Total Trades'].append(trade_analysis.total.closed if 'total' in trade_analysis and 'closed' in trade_analysis.total else 0)
            all_trades_data['Profitable Trades'].append(trade_analysis.won.total if 'won' in trade_analysis else 0)
            all_trades_data['Losing Trades'].append(trade_analysis.lost.total if 'lost' in trade_analysis else 0)
            all_trades_data['Total Profit/Loss'].append(int(round(trade_analysis.pnl.net.total)) if 'pnl' in trade_analysis and 'net' in trade_analysis.pnl else 0)
            all_trades_data['Buy Prices'].append(', '.join(map(str, strategy.buy_prices[ticker])) if strategy.buy_prices[ticker] else '')
            all_trades_data['Sell Prices'].append(', '.join(map(str, strategy.sell_prices[ticker])) if strategy.sell_prices[ticker] else '')
            all_trades_data['Month'].append(date.strftime("%Y-%m"))

        all_trades_df = pd.DataFrame(all_trades_data)
        all_trades_df.to_csv('all_trades_report.csv', index=False)
        print("All trades report saved to all_trades_report.csv")
