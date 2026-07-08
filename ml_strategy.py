"""
ml_strategy.py

A machine learning strategy: instead of hand-picked rules like moving
averages or RSI, we train a model on historical price patterns to
predict whether tomorrow's price will go up or down.

IMPORTANT METHODOLOGY -- READ BEFORE TRUSTING ANY ML BACKTEST:
We split the data chronologically into a TRAINING period and a TEST
period. The model only ever learns from the training period. The
signals we actually backtest -- the ones that produce the return,
drawdown, and Sharpe numbers you see -- only exist in the TEST
period, which the model has never seen. This is called "out-of-
sample" testing, and it's the only honest way to evaluate an ML
strategy. Training and testing on the same data is basically
cheating: the model can just memorize patterns from that exact data
that have no reason to repeat in the future.

During the training period, this function forces signal = 0 (never
holding the stock), so no fake performance gets attributed to data
the model was trained on. Only the test period at the end reflects
real, honest, previously-unseen performance.
"""

import pandas as pd
from sklearn.ensemble import RandomForestClassifier


def _build_features(price_data: pd.DataFrame) -> pd.DataFrame:
    """
    Builds predictor columns using only past/current data -- nothing
    that requires knowing the future. These are the "clues" the model
    gets to look at each day.
    """
    df = price_data.copy()

    df["return_1d"] = df["Close"].pct_change(1)
    df["return_5d"] = df["Close"].pct_change(5)

    delta = df["Close"].diff()
    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)
    avg_gain = gains.rolling(window=14).mean()
    avg_loss = losses.rolling(window=14).mean()
    df["rsi_14"] = 100 - (100 / (1 + (avg_gain / avg_loss)))

    df["ma_ratio_20"] = df["Close"] / df["Close"].rolling(window=20).mean() - 1
    df["volatility_10d"] = df["Close"].pct_change().rolling(window=10).std()

    return df


def generate_ml_signals(price_data: pd.DataFrame, test_size: float = 0.3) -> pd.DataFrame:
    """
    Trains a Random Forest classifier (a model that builds many
    decision trees and lets them vote) on the first (1 - test_size)
    portion of the data to predict next-day up/down moves. Then
    generates trading signals ONLY on the remaining test_size portion
    -- data the model never saw while training.
    """
    df = _build_features(price_data)

    feature_cols = ["return_1d", "return_5d", "rsi_14", "ma_ratio_20", "volatility_10d"]

    # Label: did price go UP the next day? This uses tomorrow's price --
    # that's fine, it's the "answer key" used only for training, never
    # something the model sees as an input feature when predicting.
    df["next_day_up"] = (df["Close"].shift(-1) > df["Close"]).astype(int)

    # Drop rows missing features (start of rolling windows) or missing
    # the label (the very last row has no "tomorrow" to check).
    clean = df.dropna(subset=feature_cols + ["next_day_up"])

    split_index = int(len(clean) * (1 - test_size))
    train = clean.iloc[:split_index]
    test = clean.iloc[split_index:]

    model = RandomForestClassifier(n_estimators=200, max_depth=5, random_state=42)
    model.fit(train[feature_cols], train["next_day_up"])

    predictions = model.predict(test[feature_cols])

    # Signal across the FULL original date range. Training-period days
    # are forced to 0 (never traded) -- only the honest, unseen test
    # period actually gets backtested.
    df["signal"] = 0
    df.loc[test.index, "signal"] = predictions
    df["position_change"] = df["signal"].diff()
    df["is_test_period"] = False
    df.loc[test.index, "is_test_period"] = True

    return df
