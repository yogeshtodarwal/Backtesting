import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# Function to fetch stock data
def fetch_data(ticker, start_date, end_date):
    df = yf.download(ticker, start=start_date, end=end_date, interval='1mo')
    return df



# Function to implement the trading strategy
def apply_strategy(df):
    df['5_EMA'] = df['Close'].ewm(span=5, adjust=False).mean()
    df['Signal'] = None
    df['StopLoss'] = None
    df['Target'] = None

    for i in range(1, len(df)):
        prev_candle = df.iloc[i-1]
        curr_candle = df.iloc[i]

        if prev_candle['High'] < prev_candle['5_EMA'] and curr_candle['Close'] > prev_candle['High']:
            df.at[df.index[i], 'Signal'] = 'Buy'
            df.at[df.index[i], 'StopLoss'] = prev_candle['Low']
            df.at[df.index[i], 'Target'] =  curr_candle['Close'] +  curr_candle['Close'] #+ 2 * (curr_candle['Close'] - prev_candle['Low'])

    df['PnL'] = None
    position = None
    entry_price = 0
    stop_loss = 0
    target = 0

    for i in range(len(df)):
        if df.at[df.index[i], 'Signal'] == 'Buy':
            position = 'Long'
            entry_price = df.at[df.index[i], 'Close']
            stop_loss = df.at[df.index[i], 'StopLoss']
            target = df.at[df.index[i], 'Target']

        if position == 'Long':
            if df.at[df.index[i], 'Low'] <= stop_loss:
                df.at[df.index[i], 'PnL'] = stop_loss - entry_price
                position = None
            elif df.at[df.index[i], 'High'] >= target:
                df.at[df.index[i], 'PnL'] = target - entry_price
                position = None

    return df

# Function to generate the report
def generate_report(df):
    trades = df.dropna(subset=['PnL'])
    total_trades = len(trades)
    profitable_trades = len(trades[trades['PnL'] > 0])
    losing_trades = len(trades[trades['PnL'] <= 0])
    total_profit = trades['PnL'].sum()

    print(f'Total Trades: {total_trades}')
    print(f'Profitable Trades: {profitable_trades}')
    print(f'Losing Trades: {losing_trades}')
    print(f'Total Profit/Loss: {total_profit}')

    return trades

# Main function to execute the strategy
def main():
    ticker = 'WIPRO.NS'
    start_date = '2020-01-01'
    end_date = '2024-06-14'

    df = fetch_data(ticker, start_date, end_date)
    df = apply_strategy(df)
    trades = generate_report(df)

    # Plotting the signals on the stock price chart
    plt.figure(figsize=(14, 7))
    plt.plot(df['Close'], label='Close Price')
    plt.plot(df['5_EMA'], label='5 EMA', linestyle='--')

    buy_signals = df[df['Signal'] == 'Buy']
    plt.scatter(buy_signals.index, buy_signals['Close'], marker='^', color='g', label='Buy Signal', s=100)

    plt.title(f'{ticker} Price and Buy Signals')
    plt.xlabel('Date')
    plt.ylabel('Price')
    plt.legend()
    plt.grid()
    plt.show()

if __name__ == '__main__':
    main()