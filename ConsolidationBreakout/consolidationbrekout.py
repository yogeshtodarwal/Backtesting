import backtrader as bt
import yfinance as yf
import pandas as pd

class ConsolidationBreakout(bt.Strategy):
    params = (
        ('consolidation_period', 3),  # Consolidation period in months
        ('target_pct', 100),          # Target percentage of the closing price on breakout
    )

    def __init__(self):
        self.buy_prices = []
        self.sell_prices = []
        self.trades = []

    def next(self):
        if not self.position:
            if self.is_consolidating():
                consolidation_period_days = self.params.consolidation_period * 22
                self.consolidation_low = min(self.data.close.get(size=consolidation_period_days))
                self.consolidation_high = max(self.data.close.get(size=consolidation_period_days))
                if self.data.close[0] > self.consolidation_high:  # Breakout condition
                    size = self.broker.get_cash() // self.data.close[0]
                    size = min(size, 30000 // self.data.close[0])
                    if size > 0:
                        self.buy(price=self.data.close[0], size=size)
                        self.buy_prices.append((self.data.datetime.date(0), self.data.close[0]))
                        self.target_price = self.data.close[0] * (1 + self.params.target_pct / 100)
                        self.stop_price = self.consolidation_low
        else:
            if self.data.close[0] >= self.target_price or self.data.close[0] <= self.stop_price:
                self.sell(price=self.data.close[0])
                self.sell_prices.append((self.data.datetime.date(0), self.data.close[0]))

    def is_consolidating(self):
        closes = self.data.close.get(size=self.params.consolidation_period * 22)
        if len(closes) < self.params.consolidation_period * 22:
            return False

        max_close = max(closes)
        min_close = min(closes)
        current_high = self.data.high[0]
        current_low = self.data.low[0]

        is_in_range = current_high < max_close and current_low > min_close

        return is_in_range and all(
            closes[i] <= max_close and closes[i] >= min_close for i in range(len(closes))
        )

    def notify_trade(self, trade):
        if trade.isclosed:
            trade_info = {
                'ticker': trade.data._name,
                'buy_date': self.buy_prices[-1][0] if self.buy_prices else None,
                'buy_price': self.buy_prices[-1][1] if self.buy_prices else None,
                'sell_date': self.sell_prices[-1][0] if self.sell_prices else None,
                'sell_price': self.sell_prices[-1][1] if self.sell_prices else None,
                'profit': trade.pnl,
                'profit_percent': (trade.pnl / trade.price) * 100 if trade.price else 0
            }
            self.trades.append(trade_info)

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
    df.rename(columns={'Adj Close': 'close'}, inplace=True)  # Ensure compatibility with Backtrader
    return df

def get_market_cap(ticker):
    try:
        ticker_info = yf.Ticker(ticker).info
        if ticker_info and 'marketCap' in ticker_info and ticker_info['marketCap'] is not None:
            return ticker_info['marketCap']
        else:
            return None
    except Exception as e:
        return None

def main():
    start_date = '2005-01-01'
    end_date = '2024-06-14'
    
    equity_file = '../equity.csv'
    stocks = pd.read_csv(equity_file)['Ticker'].tolist()

    all_trades = []

    for ticker in stocks:
        print(f'Analyzing {ticker}...')
        market_cap = get_market_cap(f'{ticker}.NS')
        if market_cap is None or market_cap < 2000000000:  # 2000 crore
            print(f"Skipping {ticker} due to low market cap or missing data.")
            continue
        
        df = fetch_data(f'{ticker}.NS', start_date, end_date)
        if df.empty:
            print(f"No data for {ticker}. Skipping.")
            continue

        data = bt.feeds.PandasData(dataname=df)

        cerebro = bt.Cerebro()
        cerebro.addstrategy(ConsolidationBreakout)
        cerebro.adddata(data)
        cerebro.broker.set_cash(100000)
        cerebro.addsizer(MaxCashSizer)

        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade')

        try:
            result = cerebro.run()
        except Exception as e:
            print(f"Error running strategy for {ticker}: {e}")
            continue

        strategy = result[0]
        trades = pd.DataFrame(strategy.trades)

        if not trades.empty:
            trades['Ticker'] = ticker
            all_trades.append(trades)

    if all_trades:
        all_trades_df = pd.concat(all_trades, ignore_index=True)
        all_trades_df.to_csv('all_trades_detailed.csv', index=False)
        
        # Summary statistics
        total_trades = len(all_trades_df)
        total_profit = all_trades_df['profit'].sum()
        average_profit_per_trade = all_trades_df['profit'].mean()
        median_profit_per_trade = all_trades_df['profit'].median()
        successful_trades = all_trades_df[all_trades_df['profit'] > 0]
        success_probability_per_trade = len(successful_trades) / total_trades if total_trades > 0 else 0

        stock_group = all_trades_df.groupby('Ticker')['profit'].sum().reset_index()
        average_profit_per_stock = stock_group['profit'].mean()
        median_profit_per_stock = stock_group['profit'].median()
        successful_stocks = stock_group[stock_group['profit'] > 0]
        success_probability_per_stock = len(successful_stocks) / len(stock_group) if len(stock_group) > 0 else 0

        summary = {
            'Total Trades': total_trades,
            'Total Stocks': len(stock_group),
            'Total Profit': total_profit,
            'Average Profit per Trade': average_profit_per_trade,
            'Median Profit per Trade': median_profit_per_trade,
            'Success Probability per Trade': success_probability_per_trade,
            'Average Profit per Stock': average_profit_per_stock,
            'Median Profit per Stock': median_profit_per_stock,
            'Success Probability per Stock': success_probability_per_stock,
        }

        summary_df = pd.DataFrame([summary])
        summary_df.to_csv('trading_summary.csv', index=False)
        print("Trading summary saved to trading_summary.csv")
    else:
        print("No trades to report.")

if __name__ == '__main__':
    main()
