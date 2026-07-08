"""
quant_ml_demo.py

Runs the walk-forward, confidence-weighted quant ML strategy on a
ticker and prints a full report: performance vs buy & hold, and --
importantly -- which features the model actually relied on.

Run it with:
    python quant_ml_demo.py

Needs a longer date range than the other tools (at least a few years)
since walk-forward validation needs enough history for the initial
training window before it can start making real predictions.
"""

import config
from data_loader import load_price_data
from quant_ml_strategy import walk_forward_predict, simulate_weighted_portfolio
from metrics import (
    calculate_total_return,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_buy_and_hold_return,
)


def main():
    ticker = config.TICKER
    print(f"Loading price data for {ticker}...")
    price_data = load_price_data(ticker, config.START_DATE, config.END_DATE)

    print("Running walk-forward validation (this retrains the model "
          "repeatedly as it moves through history -- may take a moment)...")
    tested, importance = walk_forward_predict(
        price_data, initial_train_size=252, retrain_every=21
    )

    print(f"\nWalk-forward test period: {tested.index.min().date()} to "
          f"{tested.index.max().date()} ({len(tested)} trading days)")

    print("\nSimulating a confidence-weighted portfolio (partial positions, "
          "with transaction costs)...")
    value_history, trade_log = simulate_weighted_portfolio(
        tested, config.INITIAL_CASH, transaction_cost_bps=5.0
    )

    total_return = calculate_total_return(value_history)
    max_dd = calculate_max_drawdown(value_history)
    sharpe = calculate_sharpe_ratio(value_history)
    bh_stats = calculate_buy_and_hold_return(
        price_data.loc[tested.index.min():tested.index.max()], config.INITIAL_CASH
    )

    print(f"\n{'='*55}")
    print(f"QUANT ML STRATEGY RESULTS: {ticker}")
    print(f"{'='*55}")
    print(f"{'Total return:':25}{total_return:.2f}%")
    print(f"{'Max drawdown:':25}{max_dd:.2f}%")
    print(f"{'Sharpe ratio:':25}{sharpe:.2f}")
    print(f"{'Total trades:':25}{len(trade_log)}")
    if not trade_log.empty:
        print(f"{'Total transaction costs:':25}${trade_log['cost'].sum():.2f}")
    print(f"\n--- vs Buy & Hold (same period) ---")
    print(f"{'Total return:':25}{bh_stats['total_return']:.2f}%")
    print(f"{'Max drawdown:':25}{bh_stats['max_drawdown']:.2f}%")
    print(f"{'Sharpe ratio:':25}{bh_stats['sharpe']:.2f}")
    print(f"{'='*55}\n")

    print("FEATURE IMPORTANCE (what the model actually relied on):")
    print("This is the real diagnostic quants check first -- if a model")
    print("leans almost entirely on one weird feature, that's a red flag")
    print("for overfitting rather than a genuine signal.\n")
    for feature, score in importance.items():
        bar = "#" * int(score * 100)
        print(f"  {feature:20} {score:.3f}  {bar}")


if __name__ == "__main__":
    main()
