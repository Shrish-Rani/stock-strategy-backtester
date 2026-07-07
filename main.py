"""
main.py

Run this file to execute the full backtest:
1. Load historical price data
2. Generate buy/sell signals using whichever strategy is set in config
3. Simulate trading through history
4. Print a performance report (including buy & hold comparison)
"""

import config
from data_loader import load_price_data
from strategy import (
    moving_average_crossover_signals,
    rsi_signals,
    mean_reversion_signals,
)
from backtester import run_backtest
from metrics import print_performance_report


def generate_signals(price_data):
    """
    Routes to the correct strategy function based on config.STRATEGY.
    This is the only place that needs to know all the strategies exist --
    everything else just gets handed back a signal_data DataFrame and
    doesn't care which strategy produced it.
    """
    if config.STRATEGY == "moving_average":
        return moving_average_crossover_signals(
            price_data,
            short_window=config.SHORT_WINDOW,
            long_window=config.LONG_WINDOW,
        )
    elif config.STRATEGY == "rsi":
        return rsi_signals(
            price_data,
            period=config.RSI_PERIOD,
            oversold=config.RSI_OVERSOLD,
            overbought=config.RSI_OVERBOUGHT,
        )
    elif config.STRATEGY == "mean_reversion":
        return mean_reversion_signals(
            price_data,
            window=config.MEAN_REV_WINDOW,
            entry_z=config.MEAN_REV_ENTRY_Z,
            exit_z=config.MEAN_REV_EXIT_Z,
        )
    else:
        raise ValueError(f"Unknown strategy: {config.STRATEGY}")


def main():
    print(f"Loading price data for {config.TICKER}...")
    price_data = load_price_data(config.TICKER, config.START_DATE, config.END_DATE)

    print(f"Generating trading signals using '{config.STRATEGY}' strategy...")
    signal_data = generate_signals(price_data)

    print("Running backtest simulation...")
    portfolio = run_backtest(signal_data, config.INITIAL_CASH)

    value_history = portfolio.get_value_history_df()
    print_performance_report(value_history, config.TICKER, config.INITIAL_CASH, price_data)

    trade_log = portfolio.get_trade_log_df()
    print(f"Total trades made: {len(trade_log)}")
    if not trade_log.empty:
        print(trade_log.tail(5))


if __name__ == "__main__":
    main()