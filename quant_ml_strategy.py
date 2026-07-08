"""
quant_ml_strategy.py

A more realistic version of what a systematic quant strategy actually
looks like day to day. Four upgrades over ml_strategy.py:

1. WALK-FORWARD VALIDATION instead of one single train/test split.
   Real quant shops never trust a single split -- markets change
   character over time (a "regime"), so a model trained once on old
   data quietly goes stale. Instead, the model is retrained
   periodically as time moves forward, always only using data up to
   that point, exactly mimicking how it would actually be run live.

2. PROBABILITY-WEIGHTED POSITION SIZING instead of all-in/all-out.
   If the model is only slightly confident, take a small position.
   If it's very confident, take a bigger one -- closer to real risk
   management than a binary "buy everything or sell everything."

3. A RICHER FEATURE SET and a stronger model (Gradient Boosting --
   the family that includes XGBoost/LightGBM, the industry-standard
   tools most real quant shops actually use), plus a feature
   importance report -- quants always check which signals a model is
   leaning on, both to sanity check it and catch overfitting.

4. TRANSACTION COSTS are subtracted on every trade, in basis points
   (1 bps = 0.01%), since costs meaningfully eat returns for any
   strategy that trades often.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier


def build_features(price_data: pd.DataFrame) -> pd.DataFrame:
    """A meaningfully richer feature set than ml_strategy.py's version --
    multiple momentum horizons, multiple mean-reversion windows, multiple
    volatility windows, plus MACD and Bollinger-derived signals folded
    in as raw numeric features instead of hard-coded rules."""
    df = price_data.copy()

    for horizon in [1, 3, 5, 10, 20]:
        df[f"return_{horizon}d"] = df["Close"].pct_change(horizon)

    delta = df["Close"].diff()
    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)
    avg_gain = gains.rolling(14).mean()
    avg_loss = losses.rolling(14).mean()
    df["rsi_14"] = 100 - (100 / (1 + (avg_gain / avg_loss)))

    for window in [10, 20, 50]:
        ma = df["Close"].rolling(window).mean()
        df[f"ma_ratio_{window}"] = df["Close"] / ma - 1

    for window in [5, 10, 20]:
        df[f"volatility_{window}d"] = df["Close"].pct_change().rolling(window).std()

    ma20 = df["Close"].rolling(20).mean()
    std20 = df["Close"].rolling(20).std()
    df["bollinger_z"] = (df["Close"] - ma20) / std20

    fast_ema = df["Close"].ewm(span=12, adjust=False).mean()
    slow_ema = df["Close"].ewm(span=26, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    df["macd_histogram"] = macd_line - signal_line

    if "Volume" in df.columns:
        df["volume_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()

    return df


FEATURE_COLUMNS = [
    "return_1d", "return_3d", "return_5d", "return_10d", "return_20d",
    "rsi_14",
    "ma_ratio_10", "ma_ratio_20", "ma_ratio_50",
    "volatility_5d", "volatility_10d", "volatility_20d",
    "bollinger_z", "macd_histogram",
]


def walk_forward_predict(
    price_data: pd.DataFrame,
    initial_train_size: int = 252,
    retrain_every: int = 21,
) -> tuple:
    """
    Simulates how a real systematic strategy is actually run: train
    on a window of history, predict forward for a while, retrain
    including the new data, repeat -- never letting the model see
    the future at any point.

    initial_train_size: days of history before making any real
        predictions (252 ~= 1 trading year)
    retrain_every: how often the model gets refreshed with new data
        (21 ~= about once a trading month)

    Returns (tested_data, feature_importance_report)
    """
    df = build_features(price_data)
    df["next_day_up"] = (df["Close"].shift(-1) > df["Close"]).astype(int)

    available_features = [c for c in FEATURE_COLUMNS if c in df.columns]
    clean = df.dropna(subset=available_features + ["next_day_up"]).copy()

    if len(clean) < initial_train_size + retrain_every:
        raise ValueError(
            f"Not enough data ({len(clean)} usable rows) for a walk-forward "
            f"test with initial_train_size={initial_train_size}. Use a "
            f"longer date range or reduce initial_train_size."
        )

    predicted_probability = pd.Series(index=clean.index, dtype=float)
    feature_importances = []

    start = initial_train_size
    while start < len(clean):
        end = min(start + retrain_every, len(clean))

        train = clean.iloc[:start]
        test = clean.iloc[start:end]

        model = GradientBoostingClassifier(
            n_estimators=150, max_depth=3, learning_rate=0.05, random_state=42
        )
        model.fit(train[available_features], train["next_day_up"])

        probs = model.predict_proba(test[available_features])[:, 1]
        predicted_probability.loc[test.index] = probs
        feature_importances.append(model.feature_importances_)

        start = end

    clean["predicted_probability"] = predicted_probability
    tested = clean.dropna(subset=["predicted_probability"]).copy()

    # Position sizing: convert confidence into exposure between 0 and 1.
    # 0.5 probability (a coin flip) -> 0% invested.
    # 0.75+ probability -> fully invested.
    # Real shops use more sophisticated sizing (Kelly criterion,
    # volatility targeting) but the core idea -- size by conviction,
    # not just direction -- is the same.
    tested["position_size"] = ((tested["predicted_probability"] - 0.5) * 4).clip(0, 1)

    avg_importance = np.mean(feature_importances, axis=0)
    importance_report = pd.Series(
        avg_importance, index=available_features
    ).sort_values(ascending=False)

    return tested, importance_report


def simulate_weighted_portfolio(
    signal_df: pd.DataFrame,
    initial_cash: float,
    transaction_cost_bps: float = 5.0,
) -> tuple:
    """
    Unlike backtester.py (fully in or fully out), this holds a PARTIAL
    position sized by model confidence, rebalancing toward that target
    each day, and subtracts a small transaction cost on every trade --
    real trading isn't free, and costs matter more the more you trade.
    """
    cash = initial_cash
    shares = 0
    value_history = []
    trade_log = []

    for date, row in signal_df.iterrows():
        price = row["Close"]
        target_position = row["position_size"]

        current_value = cash + shares * price
        target_value_in_stock = target_position * current_value
        target_shares = int(target_value_in_stock // price)

        shares_to_trade = target_shares - shares
        if shares_to_trade != 0:
            trade_value = abs(shares_to_trade) * price
            cost = trade_value * (transaction_cost_bps / 10000)

            if shares_to_trade > 0:
                cash -= (trade_value + cost)
                shares += shares_to_trade
                action = "BUY"
            else:
                cash += (trade_value - cost)
                shares += shares_to_trade
                action = "SELL"

            trade_log.append({
                "date": date, "action": action,
                "shares": abs(shares_to_trade), "price": price, "cost": round(cost, 2),
            })

        total_value = cash + shares * price
        value_history.append({"date": date, "total_value": total_value})

    value_history_df = pd.DataFrame(value_history).set_index("date")
    trade_log_df = pd.DataFrame(trade_log)
    return value_history_df, trade_log_df
