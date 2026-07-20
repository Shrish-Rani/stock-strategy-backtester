"""
paper_trader.py

Paper trading = simulate what the strategy would do with REAL current
prices, without using real money. Nothing here can lose (or make) you
actual money -- it just keeps a running log of what trades the
strategy WOULD have made if you'd been running it live, starting from
whenever you first ran this script for a given ticker.

How to use it:
- Run this once a day (ideally after market close, so the day's
  closing price is final):
      python paper_trader.py
- It remembers where it left off using a small JSON file per ticker,
  saved in a paper_trading_state/ folder that gets created next to
  this script. Delete a ticker's JSON file to reset and start that
  ticker's paper trading over from scratch.
- It's safe to run this multiple times on the same day -- it checks
  the date and won't double-count.
"""

import json
import os
from datetime import datetime, timedelta

import config
from data_loader import load_price_data
from strategy import (
    moving_average_crossover_signals,
    rsi_signals,
    mean_reversion_signals,
    bollinger_band_signals,
    macd_signals,
    combined_signal_strategy,
)
from ml_strategy import generate_live_ml_signal

STATE_DIR = "paper_trading_state"


def generate_signals(price_data):
    """Same routing logic as main.py / app.py -- picks the strategy
    function based on whatever is set in config.STRATEGY.

    "ml" uses generate_live_ml_signal(), the daily/live version of the
    ML strategy -- trains on everything known so far and predicts only
    today, unlike generate_ml_signals()'s honest backtest train/test
    split, which doesn't make sense for a single live day."""
    if config.STRATEGY == "ml":
        return generate_live_ml_signal(price_data)
    elif config.STRATEGY == "moving_average":
        return moving_average_crossover_signals(
            price_data, config.SHORT_WINDOW, config.LONG_WINDOW
        )
    elif config.STRATEGY == "rsi":
        return rsi_signals(
            price_data, config.RSI_PERIOD, config.RSI_OVERSOLD, config.RSI_OVERBOUGHT
        )
    elif config.STRATEGY == "mean_reversion":
        return mean_reversion_signals(
            price_data, config.MEAN_REV_WINDOW, config.MEAN_REV_ENTRY_Z, config.MEAN_REV_EXIT_Z
        )
    elif config.STRATEGY == "bollinger":
        return bollinger_band_signals(
            price_data, config.BOLLINGER_WINDOW, config.BOLLINGER_STD
        )
    elif config.STRATEGY == "macd":
        return macd_signals(
            price_data, config.MACD_FAST, config.MACD_SLOW, config.MACD_SIGNAL
        )
    elif config.STRATEGY == "combined":
        return combined_signal_strategy(
            price_data,
            config.SHORT_WINDOW, config.LONG_WINDOW,
            config.RSI_PERIOD, config.RSI_OVERSOLD, config.RSI_OVERBOUGHT,
        )
    else:
        raise ValueError(
            f"Strategy '{config.STRATEGY}' isn't supported for paper trading. "
            "Use moving_average, rsi, mean_reversion, bollinger, macd, combined, or ml."
        )


def state_file_path(ticker: str) -> str:
    return os.path.join(STATE_DIR, f"{ticker}.json")


def load_state(ticker: str, initial_cash: float) -> dict:
    """Loads saved progress for this ticker, or creates a fresh
    starting state if this is the first time we're paper trading it."""
    path = state_file_path(ticker)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)

    return {
        "ticker": ticker,
        "strategy": config.STRATEGY,
        "started_on": datetime.now().strftime("%Y-%m-%d"),
        "initial_cash": initial_cash,
        "cash": initial_cash,
        "shares": 0,
        "last_processed_date": None,
        "trade_log": [],
    }


def save_state(ticker: str, state: dict):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(state_file_path(ticker), "w") as f:
        json.dump(state, f, indent=2, default=str)


def check_ticker(ticker: str, initial_cash: float):
    print(f"\n--- {ticker} ---")
    state = load_state(ticker, initial_cash)

    # Pull enough recent history for the strategy's indicators to
    # calculate correctly (rolling averages, RSI, etc. all need a
    # lookback window of days before they produce real numbers).
    end = datetime.now()
    start = end - timedelta(days=400)
    price_data = load_price_data(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))

    signal_data = generate_signals(price_data)
    latest = signal_data.iloc[-1]
    latest_date = str(signal_data.index[-1].date())
    latest_price = float(latest["Close"])

    desired_holding = int(latest["signal"]) == 1
    currently_holding = state["shares"] > 0

    if state["last_processed_date"] == latest_date:
        print(f"Already checked {latest_date} earlier today. No new action.")
    else:
        if desired_holding and not currently_holding:
            shares_to_buy = int(state["cash"] // latest_price)
            if shares_to_buy > 0:
                cost = shares_to_buy * latest_price
                state["cash"] -= cost
                state["shares"] += shares_to_buy
                state["trade_log"].append({
                    "date": latest_date, "action": "BUY",
                    "price": latest_price, "shares": shares_to_buy,
                })
                print(f"BUY signal -> bought {shares_to_buy} shares at ${latest_price:.2f}")
        elif not desired_holding and currently_holding:
            proceeds = state["shares"] * latest_price
            print(f"SELL signal -> sold {state['shares']} shares at ${latest_price:.2f}")
            state["cash"] += proceeds
            state["trade_log"].append({
                "date": latest_date, "action": "SELL",
                "price": latest_price, "shares": state["shares"],
            })
            state["shares"] = 0
        else:
            status = "holding" if currently_holding else "sitting in cash"
            print(f"No change today. Currently {status}.")

        state["last_processed_date"] = latest_date

    total_value = state["cash"] + state["shares"] * latest_price
    total_return = (total_value - state["initial_cash"]) / state["initial_cash"] * 100

    print(f"Current price:        ${latest_price:.2f}")
    print(f"Cash:                 ${state['cash']:.2f}")
    print(f"Shares held:          {state['shares']}")
    print(f"Total value:          ${total_value:.2f}")
    print(f"Paper return so far:  {total_return:.2f}% (tracking since {state['started_on']})")

    save_state(ticker, state)


def main():
    tickers = getattr(config, "PAPER_TICKERS", getattr(config, "TICKERS", [config.TICKER]))
    print(f"Paper trading check -- strategy: {config.STRATEGY}")
    print(f"Tickers: {', '.join(tickers)}")

    for ticker in tickers:
        try:
            check_ticker(ticker, config.INITIAL_CASH)
        except Exception as e:
            print(f"Could not check {ticker}: {e}")


if __name__ == "__main__":
    main()
