"""
config.py

All the settings for a backtest run live here. Change these instead of
digging through the other files when you want to test a different
stock or strategy.
"""

# Which stock to test (used by main.py for single-run command-line tests)
TICKER = "AAPL"

# Default list of tickers shown when you open the dashboard (app.py).
# You can type any tickers you want directly in the dashboard --
# this is just what shows up pre-filled.
TICKERS = ["AAPL", "TSLA", "MSFT"]

# Which tickers paper_trader.py checks each time you run it.
# Defaults to the same list as TICKERS above -- change if you want
# to paper trade a different set than what you explore in the dashboard.
PAPER_TICKERS = ["AAPL", "TSLA", "MSFT"]

# Date range for historical data
START_DATE = "2020-01-01"
END_DATE = "2025-01-01"

# How much fake money we start with
INITIAL_CASH = 10000.0

# Which strategy to run: "moving_average", "rsi", or "mean_reversion"
STRATEGY = "moving_average"

# --- Moving average crossover settings ---
SHORT_WINDOW = 20   # short-term moving average (days)
LONG_WINDOW = 50    # long-term moving average (days)

# --- RSI settings ---
RSI_PERIOD = 14
RSI_OVERSOLD = 30    # buy when RSI drops below this
RSI_OVERBOUGHT = 70  # sell when RSI rises above this

# --- Mean reversion settings ---
MEAN_REV_WINDOW = 20     # days used for rolling average/std dev
MEAN_REV_ENTRY_Z = 1.5   # buy when price is this many std devs below average
MEAN_REV_EXIT_Z = 0.0    # sell when price reverts to (or above) this z-score