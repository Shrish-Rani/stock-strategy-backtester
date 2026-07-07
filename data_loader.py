"""
data_loader.py

Responsible for one job: getting historical price data for a stock.
Nothing in here knows about strategies or trading. It just fetches
and cleans data.
"""

import yfinance as yf
import pandas as pd


def load_price_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Downloads historical daily price data for a given stock ticker.

    Returns a DataFrame with columns: Open, High, Low, Close, Volume
    indexed by date.
    """
    data = yf.download(ticker, start=start_date, end=end_date, progress=False)

    if data.empty:
        raise ValueError(
            f"No data returned for ticker '{ticker}'. Check the symbol and date range."
        )

    # yfinance sometimes returns multi-level columns (e.g. when downloading
    # multiple tickers at once). Flatten just in case.
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    return data


if __name__ == "__main__":
    # Quick manual test: run this file directly to sanity-check the data.
    from config import TICKER, START_DATE, END_DATE

    df = load_price_data(TICKER, START_DATE, END_DATE)
    print(df.head())
    print(f"\nLoaded {len(df)} rows for {TICKER}")
