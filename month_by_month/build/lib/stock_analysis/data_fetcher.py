# stock_trading/data_fetcher.py

import yfinance as yf

def fetch_data(ticker, start_date, end_date):
    df = yf.download(ticker, start=start_date, end=end_date, interval='1d')
    return df
