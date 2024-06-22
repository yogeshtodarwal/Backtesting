import backtrader as bt
import yfinance as yf
import pandas as pd

class Supertrend(bt.Indicator):
    lines = ('supertrend', 'direction',)
    params = (
        ('period', 7),
        ('multiplier', 3),
    )

    def __init__(self):
        self.addminperiod(self.params.period)
        atr = bt.indicators.ATR(self.data, period=self.params.period)
        hl2 = (self.data.high + self.data.low) / 2
        self.lines.supertrend = bt.If(self.data.close > (hl2 - (self.params.multiplier * atr)),
                                      hl2 + (self.params.multiplier * atr),
                                      hl2 - (self.params.multiplier * atr))

    def next(self):
        if self.data.close[0] > self.lines.supertrend[0]:
            self.lines.direction[0] = 1
        elif self.data.close[0] < self.lines.supertrend[0]:
            self.lines.direction[0] = -1

class SupertrendStrategy(bt.Strategy):
    params = (
        ('period', 7),
        ('multiplier', 3),
    )

    def __init__(self):
        self.supertrend = Supertrend(self.data, period=self.params.period, multiplier=self.params.multiplier)

    def next(self):
        if not self.position:
            if self.supertrend.direction[0] == 1:
                size = self.broker.get_cash() // self.data.close[0]
                size = min(size, 30000 // self.data.close[0])
                if size > 0:
                    self.buy(size=size)
        elif self.supertrend.direction[0] == -1:
            self.sell()

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
        cerebro.addstrategy(SupertrendStrategy)
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
        trades = strategy.analyzers.trade.get_analysis()

        if trades['total']['total'] > 0:
            for i in range(trades['total']['total']):
                trade_info = {
                    'Ticker': ticker,
                    'Trade #': i + 1,
                    'Open Date': trades['trades'][i]['open_datetime'],
                    'Close Date': trades['trades'][i]['close_datetime'],
                    'Buy Price': trades['trades'][i]['price'],
                    'Sell Price': trades['trades'][i]['sell_price'],
                    'Profit': trades['trades'][i]['pnl'],
                    'Profit Percent': trades['trades'][i]['pnlcomm']
                }
                all_trades.append(trade_info)

    if all_trades:
        all_trades_df = pd.DataFrame(all_trades)
        all_trades_df.to_csv('all_trades_detailed.csv', index=False)
        
        # Summary statistics
        total_trades = len(all_trades_df)
        total_profit = all_trades_df['Profit'].sum()
        average_profit_per_trade = all_trades_df['Profit'].mean()
        median_profit_per_trade = all_trades_df['Profit'].median()
        successful_trades = all_trades_df[all_trades_df['Profit'] > 0]
        success_probability_per_trade = len(successful_trades) / total_trades if total_trades > 0 else 0

        stock_group = all_trades_df.groupby('Ticker')['Profit'].sum().reset_index()
        average_profit_per_stock = stock_group['Profit'].mean()
        median_profit_per_stock = stock_group['Profit'].median()
        successful_stocks = stock_group[stock_group['Profit'] > 0]
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
