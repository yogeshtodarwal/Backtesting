import backtrader as bt
import yfinance as yf
import pandas as pd
import os

EMA_PERIOD = 5
e_name = 'equity_full.csv'
market_cap_threshold = 20000000000  # 2000 cr Market cap threshold in USD

class BuyAboveHigh(bt.Strategy):
    params = (
        ('ema_period', EMA_PERIOD),
    )

    def __init__(self):
        self.ema = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.params.ema_period)
        self.buy_signal = bt.indicators.CrossOver(self.data.close, self.ema)
        self.buy_prices = []
        self.sell_prices = []
        self.stop_loss = None
        self.target = None
        self.trades = []  # To store trade details for reporting

    def next(self):
        if not self.position:
            if self.data.close[0] > self.data.high[-1] and self.data.high[-1] < self.ema[-1]:
                stop_loss = 0.75 * self.data.close[0]
                target = 0.5 * self.data.close[0]  # Adjusted target calculation

                size = self.broker.get_cash() // self.data.close[0]
                size = min(size, 30000 // self.data.close[0])  # Ensure size is within max_cash constraint
                if size > 0:
                    print(f"Buying {size} shares of {self.data._name} at {self.data.close[0]} for a total of {size * self.data.close[0]}")
                    self.buy(price=self.data.close[0], size=size)
                    self.buy_prices.append((self.data.datetime.date(0), self.data.close[0]))
                    self.stop_loss = stop_loss
                    self.target = target
        else:
            if self.data.close[0] >= self.target or self.data.close[0] <= self.stop_loss:
                print(f"Selling {self.position.size} shares of {self.data._name} at {self.data.close[0]}")
                self.sell(price=self.data.close[0])
                self.sell_prices.append((self.data.datetime.date(0), self.data.close[0]))
                self.stop_loss = None
                self.target = None

    def notify_trade(self, trade):
        if trade.isclosed:
            trade_info = {
                'ticker': trade.data._name,
                'buy_date': self.buy_prices[-1][0] if self.buy_prices else None,
                'buy_price': self.buy_prices[-1][1] if self.buy_prices else None,
                'sell_date': self.sell_prices[-1][0] if self.sell_prices else None,
                'sell_price': self.sell_prices[-1][1] if self.sell_prices else None,
                'profit': trade.pnl,
                'profit_percent': (trade.pnl / trade.price) * 100
            }
            self.trades.append(trade_info)
            print(f'Closed: {trade.data._name}, Profit: {trade.pnl:.2f}, Buy Price: {trade_info["buy_price"]:.2f}, Sell Price: {trade_info["sell_price"]:.2f}')

class MaxCashSizer(bt.Sizer):
    params = (
        ('max_cash', 30000),  # Maximum cash to use per trade
    )

    def _getsizing(self, comminfo, cash, data, isbuy):
        if isbuy:
            available_cash = min(self.params.max_cash, cash)
            size = available_cash // data.close[0]
            print(f"Calculating size: available_cash = {available_cash}, data.close[0] = {data.close[0]}, size = {size}")
            return size
        return self.broker.getposition(data).size

def fetch_data(ticker, start_date, end_date):
    df = yf.download(ticker, start=start_date, end=end_date, interval='1mo')
    return df

def get_market_cap(ticker):
    try:
        ticker_info = yf.Ticker(ticker).info
        if ticker_info and 'marketCap' in ticker_info and ticker_info['marketCap'] is not None:
            return ticker_info['marketCap']
        else:
            print(f"Market cap information not available for {ticker}")
            return None
    except Exception as e:
        print(f"Error fetching market cap for {ticker}: {e}")
        return None

def main():
    start_date = '2005-01-01'
    end_date = '2024-06-14'
    
    # Read stock tickers from CSV file
    equity_file = e_name
    stocks = pd.read_csv(equity_file)['Ticker'].tolist()

    all_trades = []
    completed_trades = []

    for ticker in stocks:
        print(f'Analyzing {ticker}...')
        # Check market capitalization
        market_cap = get_market_cap(f'{ticker}.NS')  # Adjust suffix according to your data source
        if market_cap is None or market_cap < market_cap_threshold:
            print(f"Skipping {ticker} due to low market cap or missing data.")
            continue
        
        df = fetch_data(f'{ticker}.NS', start_date, end_date)
        if df.empty:
            print(f"No data for {ticker}. Skipping.")
            continue

        if len(df) < EMA_PERIOD:  # Check if there's enough data for EMA calculation
            print(f"Not enough data for {ticker}. Skipping.")
            continue

        data = bt.feeds.PandasData(dataname=df)

        cerebro = bt.Cerebro()
        cerebro.addstrategy(BuyAboveHigh)
        cerebro.adddata(data)
        cerebro.broker.set_cash(100000)  # Initial cash, adjust as needed
        cerebro.addsizer(MaxCashSizer)  # Use the custom sizer

        # Add trade analyzer
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade')

        # Run the strategy
        try:
            result = cerebro.run()
        except Exception as e:
            print(f"Error running strategy for {ticker}: {e}")
            continue

        # Generate report
        strategy = result[0]
        trade_analysis = strategy.analyzers.trade.get_analysis()

        trades = pd.DataFrame(strategy.trades)

        if not trades.empty:
            trade_summary = pd.DataFrame({
                'Ticker': [ticker],
                'Total Trades': [trade_analysis.total.closed if 'total' in trade_analysis and 'closed' in trade_analysis.total else 0],
                'Profitable Trades': [trade_analysis.won.total if 'won' in trade_analysis else 0],
                'Losing Trades': [trade_analysis.lost.total if 'lost' in trade_analysis else 0],
                'Total Profit/Loss': [int(round(trade_analysis.pnl.net.total)) if 'pnl' in trade_analysis and 'net' in trade_analysis.pnl else 0],
                'Profit Percentage': [round((trade_analysis.pnl.net.total / 100000) * 100, 2) if 'pnl' in trade_analysis and 'net' in trade_analysis.pnl else 0],
                'Buy Prices': [', '.join(map(str, trades['buy_price'].dropna().tolist()))],
                'Sell Prices': [', '.join(map(str, trades['sell_price'].dropna().tolist()))],
            })

            completed_trades.append(trades)
        else:
            trade_summary = pd.DataFrame({
                'Ticker': [ticker],
                'Total Trades': [0],
                'Profitable Trades': [0],
                'Losing Trades': [0],
                'Total Profit/Loss': [0],
                'Profit Percentage': [0],
                'Buy Prices': [''],
                'Sell Prices': [''],
            })

        all_trades.append(trade_summary)

    # Concatenate all trades into a single DataFrame
    if all_trades:
        all_trades_df = pd.concat(all_trades, ignore_index=True)
        all_trades_df.to_csv('all_trades_report.csv', index=False)
        print("All trades report saved to all_trades_report.csv")
    else:
        print("No trades to report.")

    # Save completed trades report
    if completed_trades:
        completed_trades_df = pd.concat(completed_trades, ignore_index=True)
        completed_trades_df.to_csv('completed_trades_report.csv', index=False)
        print("Completed trades report saved to completed_trades_report.csv")
    else:
        print("No completed trades to report.")

if __name__ == '__main__':
    main()