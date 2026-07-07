"""
metrics.py

Turns a portfolio's value history into a few standard numbers people
in finance actually use to judge a strategy:

- Total return: how much money did we make, in %?
- Max drawdown: what's the worst peak-to-valley drop we experienced?
  (This matters because a strategy that returns 50% but drops 40%
  along the way is a much scarier ride than one that returns 30%
  steadily.)
- Sharpe ratio: return per unit of risk. Roughly: (average daily
  return / volatility of daily returns), scaled to a yearly number.
  Higher is generally better -- it means you got more return for
  the bumpiness you endured.
- Buy & hold comparison: what if we'd just bought on day one and
  never touched it? This is the benchmark a strategy has to beat
  to be worth the added complexity and risk.
"""

import numpy as np
import pandas as pd


def calculate_total_return(value_history: pd.DataFrame) -> float:
    start_value = value_history["total_value"].iloc[0]
    end_value = value_history["total_value"].iloc[-1]
    return (end_value - start_value) / start_value * 100


def calculate_max_drawdown(value_history: pd.DataFrame) -> float:
    values = value_history["total_value"]
    # running_max = the highest value seen so far at each point in time
    running_max = values.cummax()
    # drawdown = how far below that peak we currently are, as a %
    drawdown = (values - running_max) / running_max
    return drawdown.min() * 100  # most negative number = worst drop


def calculate_sharpe_ratio(value_history: pd.DataFrame, risk_free_rate: float = 0.0) -> float:
    daily_returns = value_history["total_value"].pct_change().dropna()

    if daily_returns.std() == 0:
        return 0.0

    # Annualize: there are ~252 trading days in a year
    excess_daily_return = daily_returns.mean() - (risk_free_rate / 252)
    sharpe = (excess_daily_return / daily_returns.std()) * np.sqrt(252)
    return sharpe


def calculate_buy_and_hold_return(price_data: pd.DataFrame, initial_cash: float) -> dict:
    """
    Simulates the simplest possible strategy: buy as many shares as
    possible on day one, hold until the last day, sell. No trading,
    no signals, nothing fancy. This is the benchmark every real
    strategy has to beat to be worth the added complexity and risk.
    """
    start_price = price_data["Close"].iloc[0]
    end_price = price_data["Close"].iloc[-1]

    shares_bought = int(initial_cash // start_price)
    leftover_cash = initial_cash - (shares_bought * start_price)
    end_value = leftover_cash + (shares_bought * end_price)

    total_return = (end_value - initial_cash) / initial_cash * 100

    bh_value_history = price_data[["Close"]].copy()
    bh_value_history["total_value"] = leftover_cash + (shares_bought * bh_value_history["Close"])
    bh_value_history = bh_value_history[["total_value"]]

    return {
        "end_value": end_value,
        "total_return": total_return,
        "max_drawdown": calculate_max_drawdown(bh_value_history),
        "sharpe": calculate_sharpe_ratio(bh_value_history),
    }


def print_performance_report(
    value_history: pd.DataFrame,
    ticker: str,
    initial_cash: float,
    price_data: pd.DataFrame = None,
):
    total_return = calculate_total_return(value_history)
    max_drawdown = calculate_max_drawdown(value_history)
    sharpe = calculate_sharpe_ratio(value_history)
    end_value = value_history["total_value"].iloc[-1]

    print(f"\n{'='*50}")
    print(f"BACKTEST RESULTS: {ticker}")
    print(f"{'='*50}")
    print(f"{'Starting cash:':20}${initial_cash:,.2f}")
    print(f"{'Ending value:':20}${end_value:,.2f}")
    print(f"{'Total return:':20}{total_return:.2f}%")
    print(f"{'Max drawdown:':20}{max_drawdown:.2f}%")
    print(f"{'Sharpe ratio:':20}{sharpe:.2f}")

    if price_data is not None:
        bh = calculate_buy_and_hold_return(price_data, initial_cash)
        bh_end_value = bh["end_value"]
        bh_total_return = bh["total_return"]
        bh_max_drawdown = bh["max_drawdown"]
        bh_sharpe = bh["sharpe"]

        print("\n--- vs. Buy & Hold ---")
        print(f"{'Ending value:':20}${bh_end_value:,.2f}")
        print(f"{'Total return:':20}{bh_total_return:.2f}%")
        print(f"{'Max drawdown:':20}{bh_max_drawdown:.2f}%")
        print(f"{'Sharpe ratio:':20}{bh_sharpe:.2f}")

        beat_bh = total_return > bh_total_return
        diff = abs(total_return - bh_total_return)
        result_word = "BEAT" if beat_bh else "UNDERPERFORMED"
        print(f"\nStrategy {result_word} buy & hold by {diff:.2f} percentage points.")

    print(f"{'='*50}\n")