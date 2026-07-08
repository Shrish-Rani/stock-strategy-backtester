"""
portfolio_backtest.py

Runs a backtest across MULTIPLE tickers at once, splitting your
starting cash evenly between them, then combines the results into
one overall portfolio value curve.

Why this matters: testing stocks one at a time hides something
important -- diversification. If AAPL drops 20% one month but TSLA
gains 20% the same month, a combined portfolio barely notices. But
each ticker tested alone would show that swing in full. Real
portfolio risk is about how stocks move TOGETHER, not just how each
one moves on its own.
"""

import pandas as pd

from data_loader import load_price_data
from backtester import run_backtest


def run_portfolio_backtest(
    tickers: list,
    generate_signals_fn,
    start_date: str,
    end_date: str,
    initial_cash: float,
) -> dict:
    """
    generate_signals_fn: a function that takes price_data and returns
    signal_data, already configured with whatever strategy and
    parameters you want. This function doesn't need to know which
    strategy is running -- same "don't need to know" separation used
    throughout this project.

    Returns a dict with:
      - 'combined_value_history': the whole portfolio's value added
        together, day by day
      - 'per_ticker': a dict of per-ticker results (value history,
        trade log, price data) in case you want to inspect one stock
        individually
    """
    cash_per_ticker = initial_cash / len(tickers)
    per_ticker_results = {}

    for ticker in tickers:
        price_data = load_price_data(ticker, start_date, end_date)
        signal_data = generate_signals_fn(price_data)
        portfolio = run_backtest(signal_data, cash_per_ticker)
        value_history = portfolio.get_value_history_df()

        per_ticker_results[ticker] = {
            "value_history": value_history,
            "trade_log": portfolio.get_trade_log_df(),
            "price_data": price_data,
        }

    # Combine every ticker's value history into one total portfolio
    # curve. Align by date and forward-fill any gaps, in case one
    # ticker is missing a trading day another one has.
    combined = None
    for ticker, result in per_ticker_results.items():
        vh = result["value_history"].rename(columns={"total_value": ticker})
        combined = vh if combined is None else combined.join(vh, how="outer")

    combined = combined.sort_index().ffill().bfill()
    combined["total_value"] = combined[list(per_ticker_results.keys())].sum(axis=1)

    return {
        "combined_value_history": combined[["total_value"]],
        "per_ticker": per_ticker_results,
    }
