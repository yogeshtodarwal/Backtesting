import backtrader as bt
import yfinance as yf
import pandas as pd
import os
import quantstats

class BuyAboveHigh(bt.Strategy):
    params = (
        ('ema_period', 5),
    )

    def __init__(self):
        self.ema = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.params.ema_period)
        self.buy_signal = bt.indicators.CrossOver(self.data.close, self.ema)
        self.order = None

    def next(self):
        if self.order:  # Check if there is an open order
            return

        if not self.position:  # Check if there is no open position
            if self.data.close[0] > self.data.high[-1] and self.data.high[-1] < self.ema[-1]:
                stop_loss = self.data.close[0] * 0.80  # 20% below the current price
                target = self.data.close[0] * 2  # 100% above the current price

                size = self.broker.get_cash() // self.data.close[0]
                if size > 0:
                    self.order = self.buy_bracket(price=self.data.close[0], stopprice=stop_loss, limitprice=target, size=size)

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            self.order = None

class MaxCashSizer(bt.Sizer):
    params = (
        ('max_cash', 30000),  # Maximum cash to use per trade
    )

    def _getsizing(self, comminfo, cash, data, isbuy):
        if isbuy:
            available_cash = min(self.params.max_cash, cash)
            size = available_cash // data.close[0]
            return size
        return self.broker.getposition(data).size

def fetch_data(ticker, start_date, end_date):
    df = yf.download(ticker, start=start_date, end=end_date, interval='1mo')
    return df

def main():
    start_date = '2010-01-01'
    end_date = '2023-01-01'
    
    # Read stock tickers from CSV file
    equity_file = 'equity.csv'
    stocks = pd.read_csv(equity_file)['Ticker'].tolist()

    all_trades = []

    for ticker in stocks:
        print(f'Analyzing {ticker}...')
        df = fetch_data(f'{ticker}.NS', start_date, end_date)
        if df.empty:
            print(f"No data for {ticker}. Skipping.")
            continue

        if len(df) < 5:  # Check if there's enough data for EMA calculation
            print(f"Not enough data for {ticker}. Skipping.")
            continue

        data = bt.feeds.PandasData(dataname=df)

        cerebro = bt.Cerebro()
        cerebro.addstrategy(BuyAboveHigh)
        cerebro.adddata(data)
        cerebro.broker.set_cash(1000000)  # Initial cash, adjust as needed
        cerebro.addsizer(MaxCashSizer)  # Use the custom sizer

        # Add trade analyzer
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade')
        cerebro.addanalyzer(bt.analyzers.PyFolio, _name='pyfolio')

        # Run the strategy
        try:
            result = cerebro.run()
        except Exception as e:
            print(f"Error running strategy for {ticker}: {e}")
            continue

        # Generate report
        trade_analysis = result[0].analyzers.trade.get_analysis()

        trades = pd.DataFrame({
            'Ticker': [ticker],
            'Total Trades': [trade_analysis.total.total if 'total' in trade_analysis.total else 0],
            'Profitable Trades': [trade_analysis.won.total if 'won' in trade_analysis else 0],
            'Losing Trades': [trade_analysis.lost.total if 'lost' in trade_analysis else 0],
            'Total Profit/Loss': [trade_analysis.pnl.net.total if 'pnl' in trade_analysis and 'net' in trade_analysis.pnl else 0],
        })

        all_trades.append(trades)

        # Use QuantStats to generate a detailed report
        pyfoliozer = result[0].analyzers.getbyname('pyfolio')
        returns, positions, transactions, gross_lev = pyfoliozer.get_pf_items()
        returns.index = returns.index.tz_convert(None)  # Remove timezone information
        quantstats.reports.html(returns, output=f'{ticker}_report.html', title=f'{ticker} Strategy Performance Report')

    # Concatenate all trades into a single DataFrame
    if all_trades:
        all_trades_df = pd.concat(all_trades, ignore_index=True)
        all_trades_df.to_csv('all_trades_report.csv', index=False)
        print("All trades report saved to all_trades_report.csv")
    else:
        print("No trades to report.")

if __name__ == '__main__':
    main()
