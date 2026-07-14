"""
risk_management.py

A risk-management layer that can wrap ANY strategy's signals, adding
stop-loss and take-profit rules on top -- without changing the
strategy's own logic at all.

Why this matters: every strategy you've built so far only exits a
position when its OWN signal flips (moving averages cross back, RSI
climbs back above 70, etc.). That can be slow. If you buy a stock
and it immediately drops 15%, a moving average strategy might not
say "sell" for weeks, by which point you've absorbed a much bigger
loss than necessary. A stop-loss forces an exit early, capping how
much any single trade can hurt you -- this is one of the most
universally used real risk-management tools in professional trading.

A take-profit does the opposite: it locks in gains early once a
trade has moved far enough in your favor, rather than greedily
waiting for the signal to eventually reverse (which sometimes gives
back a big chunk of the gain first).
"""

import pandas as pd


def apply_stop_loss_take_profit(
    signal_data: pd.DataFrame,
    stop_loss_pct: float = -8.0,
    take_profit_pct: float = 15.0,
) -> pd.DataFrame:
    """
    Takes the signal_data from ANY strategy (moving average, RSI,
    MACD, whatever -- anything with 'Close' and 'signal' columns) and
    overrides it: if a position has moved against you by more than
    stop_loss_pct, or in your favor by more than take_profit_pct,
    force an exit immediately, regardless of what the underlying
    strategy's signal says.

    stop_loss_pct: negative number, e.g. -8.0 means "exit if down 8%
        from entry price"
    take_profit_pct: positive number, e.g. 15.0 means "exit if up 15%
        from entry price"

    Returns a new DataFrame with 'signal' and 'position_change'
    recalculated to reflect these forced exits. Re-entry still
    follows the underlying strategy's own signal afterward.
    """
    df = signal_data.copy()

    holding = False
    entry_price = None
    new_signal = []
    exit_reason = []

    for price, original_signal in zip(df["Close"], df["signal"]):
        reason = None

        if not holding:
            if original_signal == 1:
                holding = True
                entry_price = price
        else:
            change_pct = (price - entry_price) / entry_price * 100

            if change_pct <= stop_loss_pct:
                holding = False
                entry_price = None
                reason = "stop_loss"
            elif change_pct >= take_profit_pct:
                holding = False
                entry_price = None
                reason = "take_profit"
            elif original_signal == 0:
                # The underlying strategy itself says exit -- honor that too.
                holding = False
                entry_price = None
                reason = "strategy_signal"

        new_signal.append(1 if holding else 0)
        exit_reason.append(reason)

    df["signal"] = new_signal
    df["position_change"] = df["signal"].diff()
    df["exit_reason"] = exit_reason

    return df
