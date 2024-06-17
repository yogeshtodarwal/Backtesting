# stock_trading/main.py

from .pipeline import TradingPipeline

def main():
    start_date = '2007-01-01'
    end_date = '2024-06-14'
    equity_file = 'equity.csv'

    pipeline = TradingPipeline(start_date, end_date, equity_file)
    pipeline.run()

if __name__ == '__main__':
    main()
