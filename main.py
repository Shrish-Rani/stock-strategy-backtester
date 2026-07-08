"""
main.py

Run this file to execute the full backtest:
1. Load historical price data
2. Generate buy/sell signals using whichever strategy is set in config
3. Simulate trading through history
4. Print a performance report (including buy & hold comparison)

Note: the machine learning strategy and multi-stock portfolio mode
are available in the dashboard (app.py) since they benefit from
sliders/visuals, but the ML strategy can also be run here -- set
STRATEGY = "ml" in config.py.
"""

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
from ml_strategy import generate_ml_signals
from backtester import run_backtest
from metrics import print_performance_report


def generate_signals(price_data):
    """
    Routes to the correct strategy function based on config.STRATEGY.
    This is the only place that needs to know all the strategies exist
    -- everything else just gets handed back a signal_data DataFrame
    and doesn't care which strategy produced it.
    """
    if config.STRATEGY == "moving_average":
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
    elif config.STRATEGY == "ml":
        return generate_ml_signals(price_data, config.ML_TEST_SIZE)
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
