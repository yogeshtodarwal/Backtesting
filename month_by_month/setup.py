# setup.py

from setuptools import setup, find_packages

setup(
    name='stock_trading',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'backtrader',
        'yfinance',
        'pandas',
    ],
    entry_points={
        'console_scripts': [
            'stock_trading = stock_trading.main:main',
        ],
    },
)
