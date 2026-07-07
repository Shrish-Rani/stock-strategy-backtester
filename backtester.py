"""
backtester.py

The simulation loop. This is the piece that ties strategy signals
to actual portfolio actions, walking through history one day at a time
-- exactly like it would happen in real life, just compressed into
a fast loop instead of waiting years for it to play out.
"""

import pandas as pd
from portfolio import Portfolio


def run_backtest(signal_data: pd.DataFrame, initial_cash: float) -> Portfolio:
    """
    signal_data must have columns: 'Close', 'position_change'
    (this comes from strategy.py's moving_average_crossover_signals)

    position_change == 1  -> BUY today
    position_change == -1 -> SELL today
    anything else         -> do nothing, just record value
    """
    portfolio = Portfolio(initial_cash)

    for date, row in signal_data.iterrows():
        price = row["Close"]

        if row["position_change"] == 1:
            portfolio.buy(date, price)
        elif row["position_change"] == -1:
            portfolio.sell(date, price)

        portfolio.record_value(date, price)

    return portfolio
