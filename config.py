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
TICKERS = ["AAPL", "TSLA", "MSFT", "MCD"]

# Which tickers paper_trader.py checks each time you run it.
# Defaults to the same list as TICKERS above -- change if you want
# to paper trade a different set than what you explore in the dashboard.
PAPER_TICKERS = ["AAPL", "TSLA", "MSFT", "MCD"]

# Date range for historical data
from datetime import datetime

START_DATE = "2020-01-01"

# NOTE: END_DATE below is computed once, the moment this file is first
# imported. That's fine for scripts you run fresh each time (main.py,
# paper_trader.py, etc. -- each run is a brand-new process). But for
# a long-running server like the Streamlit dashboard, this value gets
# "frozen" at whatever day the server last started, since Python only
# runs this file's code once per process lifetime. If you need a
# truly always-fresh date inside a long-running app, call
# get_current_date() below instead of reading END_DATE directly.
END_DATE = datetime.now().strftime("%Y-%m-%d")


def get_current_date() -> str:
    """Always returns TODAY's actual date, recalculated fresh every
    time this function is called -- safe to use even inside a
    long-running process like the Streamlit dashboard."""
    return datetime.now().strftime("%Y-%m-%d")

# How much fake money we start with
INITIAL_CASH = 10000.0

# Which strategy to run: "moving_average", "rsi", "mean_reversion",
# "bollinger", "macd", "combined", or "ml"
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

# --- Bollinger Bands settings ---
BOLLINGER_WINDOW = 20
BOLLINGER_STD = 2.0

# --- MACD settings ---
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# --- Machine learning strategy settings ---
ML_TEST_SIZE = 0.3  # fraction of data held out as unseen "test" period
