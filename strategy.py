"""
strategy.py

Each strategy function takes price data and returns a DataFrame with:
  - 'signal': 1 = we want to be holding the stock today, 0 = cash
  - 'position_change': +1 = BUY today, -1 = SELL today, 0 = do nothing

This is the only contract the backtester cares about. As long as a
strategy function follows this shape, backtester.py never needs to
change, no matter how many strategies we add.
"""

import pandas as pd


def moving_average_crossover_signals(
    price_data: pd.DataFrame,
    short_window: int,
    long_window: int,
) -> pd.DataFrame:
    """
    Buy when the short-term average price crosses above the long-term
    average (upward momentum). Sell when it crosses back below.
    """
    df = price_data.copy()

    df["short_ma"] = df["Close"].rolling(window=short_window).mean()
    df["long_ma"] = df["Close"].rolling(window=long_window).mean()

    df["signal"] = 0
    df.loc[df["short_ma"] > df["long_ma"], "signal"] = 1

    df["position_change"] = df["signal"].diff()

    return df


def rsi_signals(
    price_data: pd.DataFrame,
    period: int = 14,
    oversold: int = 30,
    overbought: int = 70,
) -> pd.DataFrame:
    """
    RSI (Relative Strength Index) measures how hard a stock has been
    bought or sold recently, on a 0-100 scale.

    How RSI is calculated:
    1. Look at each day's price change (up or down) over the last
       `period` days.
    2. Average the size of the "up" days and average the size of the
       "down" days separately.
    3. RSI = 100 - (100 / (1 + average_gain / average_loss))

    Strategy: buy when RSI drops below `oversold` (stock has been sold
    off hard, may bounce). Sell when RSI climbs above `overbought`
    (stock has been bought up hard, may pull back).

    Unlike moving average crossover, RSI crossing a threshold is a
    single moment in time, not an ongoing state -- so we need to track
    "are we currently holding the stock?" day by day.
    """
    df = price_data.copy()

    delta = df["Close"].diff()
    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)

    avg_gain = gains.rolling(window=period).mean()
    avg_loss = losses.rolling(window=period).mean()

    relative_strength = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + relative_strength))

    # Walk day by day tracking whether we're currently holding.
    # This is a "state machine": once we buy, we stay in the trade
    # until RSI says to sell, regardless of what RSI does in between.
    holding = False
    signals = []
    for rsi_value in df["rsi"]:
        if pd.isna(rsi_value):
            signals.append(0)
            continue
        if not holding and rsi_value < oversold:
            holding = True
        elif holding and rsi_value > overbought:
            holding = False
        signals.append(1 if holding else 0)

    df["signal"] = signals
    df["position_change"] = df["signal"].diff()

    return df


def mean_reversion_signals(
    price_data: pd.DataFrame,
    window: int = 20,
    entry_z: float = 1.5,
    exit_z: float = 0.0,
) -> pd.DataFrame:
    """
    Mean reversion bets that prices wander away from their recent
    average and then drift back to it.

    How it works:
    1. Calculate the rolling average price and rolling standard
       deviation over `window` days.
    2. Calculate the z-score: how many standard deviations today's
       price is away from that average.
       z-score = (price - rolling_average) / rolling_std_dev
    3. A very negative z-score means the price has dropped unusually
       far below its own recent average.

    Strategy: buy when z-score drops below -entry_z (price is
    unusually cheap relative to its recent average). Sell once the
    z-score climbs back up to exit_z (price has reverted).
    """
    df = price_data.copy()

    rolling_mean = df["Close"].rolling(window=window).mean()
    rolling_std = df["Close"].rolling(window=window).std()

    df["z_score"] = (df["Close"] - rolling_mean) / rolling_std

    holding = False
    signals = []
    for z in df["z_score"]:
        if pd.isna(z):
            signals.append(0)
            continue
        if not holding and z < -entry_z:
            holding = True
        elif holding and z > exit_z:
            holding = False
        signals.append(1 if holding else 0)

    df["signal"] = signals
    df["position_change"] = df["signal"].diff()

    return df