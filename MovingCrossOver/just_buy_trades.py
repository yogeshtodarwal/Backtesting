import backtrader as bt
import yfinance as yf
import pandas as pd
import itertools

class MovingAverageCrossover(bt.Strategy):
    params = (
        ('fast_period', 10),
        ('slow_period', 30),
    )

    def __init__(self):
        self.fast_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.params.fast_period)
        self.slow_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.params.slow_period)
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)

        self.buy_signals = []

    def next(self):
        if self.crossover > 0:  # Fast MA crosses above Slow MA
            self.buy_signals.append((self.data.datetime.date(0), self.data.close[0]))

def fetch_data(ticker, start_date, end_date):
    df = yf.download(ticker, start=start_date, end=end_date, interval='1mo')
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
    start_date = '2000-01-01'
    end_date = '2024-06-19'
    
    equity_file = '../equity_full.csv'
    stocks = pd.read_csv(equity_file)['Ticker'].tolist()

    all_buy_signals = []

    # Hyperparameter grid
    fast_periods = [25] #[5, 7, 10, 13, 15, 20, 23, 25]   
    slow_periods = [30] #[30, 33, 35, 37, 40, 43, 45, 47, 50, 52]      
    hyperparams = list(itertools.product(fast_periods, slow_periods))

    for ticker in stocks:
        print(f'Analyzing {ticker}...')
        market_cap = get_market_cap(f'{ticker}.NS')
        if market_cap is None or market_cap < 2000000000: #2000 crore
            print(f"Skipping {ticker} due to low market cap or missing data.")
            continue
        
        df = fetch_data(f'{ticker}.NS', start_date, end_date)
        if df.empty:
            print(f"No data for {ticker}. Skipping.")
            continue

        if len(df) < max(fast_periods + slow_periods):
            print(f"Not enough data for {ticker}. Skipping.")
            continue

        for fast_period, slow_period in hyperparams:
            print(f"Testing {ticker} with fast_period={fast_period} and slow_period={slow_period}")
            
            data = bt.feeds.PandasData(dataname=df)

            cerebro = bt.Cerebro()
            cerebro.addstrategy(MovingAverageCrossover, fast_period=fast_period, slow_period=slow_period)
            cerebro.adddata(data)
            cerebro.broker.set_cash(100000)

            try:
                result = cerebro.run()
            except Exception as e:
                print(f"Error running strategy for {ticker}: {e}")
                continue

            strategy = result[0]
            buy_signals = pd.DataFrame(strategy.buy_signals, columns=['Buy Date', 'Buy Price'])

            if not buy_signals.empty:
                buy_signals['Ticker'] = ticker
                buy_signals['Fast Period'] = fast_period
                buy_signals['Slow Period'] = slow_period
                all_buy_signals.append(buy_signals)

    if all_buy_signals:
        all_buy_signals_df = pd.concat(all_buy_signals, ignore_index=True)
        all_buy_signals_df.to_csv('just_buy_signals.csv', index=False)
        print("Buy signals saved to just_buy_signals.csv")
    else:
        print("No buy signals to report.")

if __name__ == '__main__':
    main()
