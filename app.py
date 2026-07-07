"""
app.py

An interactive web dashboard for the backtester, built with Streamlit.

Run it with:
    streamlit run app.py

This does NOT replace main.py -- main.py is still useful for quick
single-run tests from the command line. This file is for exploring:
trying different tickers, strategies, and parameters, and seeing
charts instead of just printed numbers.
"""

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

import config
from data_loader import load_price_data
from strategy import (
    moving_average_crossover_signals,
    rsi_signals,
    mean_reversion_signals,
)
from backtester import run_backtest
from metrics import (
    calculate_total_return,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_buy_and_hold_return,
)


# Caching means if you re-run the same ticker/date range twice, we don't
# hit Yahoo Finance again -- Streamlit remembers the result.
@st.cache_data
def get_price_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    return load_price_data(ticker, start, end)


st.set_page_config(page_title="Strategy Backtester", layout="wide")
st.title("Stock Strategy Backtester")

# ---------------- Sidebar: all user controls live here ----------------
st.sidebar.header("Settings")

default_tickers = ", ".join(getattr(config, "TICKERS", [config.TICKER]))
tickers_input = st.sidebar.text_input(
    "Tickers (comma-separated)", value=default_tickers
)
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

strategy_name = st.sidebar.selectbox(
    "Strategy",
    ["Moving Average Crossover", "RSI", "Mean Reversion"],
)

start_date = st.sidebar.date_input(
    "Start date", pd.to_datetime(config.START_DATE).date()
)
end_date = st.sidebar.date_input(
    "End date", pd.to_datetime(config.END_DATE).date()
)
initial_cash = st.sidebar.number_input(
    "Initial cash ($)", value=float(config.INITIAL_CASH), step=1000.0
)

st.sidebar.subheader("Strategy Parameters")

if strategy_name == "Moving Average Crossover":
    short_window = st.sidebar.slider("Short window (days)", 5, 60, config.SHORT_WINDOW)
    long_window = st.sidebar.slider("Long window (days)", 20, 250, config.LONG_WINDOW)
elif strategy_name == "RSI":
    rsi_period = st.sidebar.slider("RSI period (days)", 5, 30, config.RSI_PERIOD)
    oversold = st.sidebar.slider("Oversold threshold", 10, 40, config.RSI_OVERSOLD)
    overbought = st.sidebar.slider("Overbought threshold", 60, 90, config.RSI_OVERBOUGHT)
else:  # Mean Reversion
    mr_window = st.sidebar.slider("Rolling window (days)", 5, 60, config.MEAN_REV_WINDOW)
    entry_z = st.sidebar.slider("Entry z-score", 0.5, 3.0, config.MEAN_REV_ENTRY_Z, step=0.1)
    exit_z = st.sidebar.slider("Exit z-score", -1.0, 1.0, config.MEAN_REV_EXIT_Z, step=0.1)

run_clicked = st.sidebar.button("Run Backtest", type="primary")


def generate_signals(price_data: pd.DataFrame) -> pd.DataFrame:
    """Routes to whichever strategy the user picked in the sidebar."""
    if strategy_name == "Moving Average Crossover":
        return moving_average_crossover_signals(price_data, short_window, long_window)
    elif strategy_name == "RSI":
        return rsi_signals(price_data, rsi_period, oversold, overbought)
    else:
        return mean_reversion_signals(price_data, mr_window, entry_z, exit_z)


def build_buy_and_hold_curve(price_data: pd.DataFrame, initial_cash: float) -> pd.Series:
    """Same math as calculate_buy_and_hold_return, but returns the
    day-by-day value curve instead of just the final number, so we
    can plot it."""
    start_price = price_data["Close"].iloc[0]
    shares = int(initial_cash // start_price)
    leftover_cash = initial_cash - (shares * start_price)
    return leftover_cash + shares * price_data["Close"]


# ---------------- Main area: results appear here after clicking Run ----------------
if not run_clicked:
    st.info("Set your tickers and strategy in the sidebar, then click **Run Backtest**.")
else:
    if not tickers:
        st.error("Enter at least one ticker symbol.")

    for ticker in tickers:
        st.header(ticker)

        try:
            price_data = get_price_data(ticker, str(start_date), str(end_date))
        except Exception as e:
            st.error(f"Could not load data for {ticker}: {e}")
            continue

        signal_data = generate_signals(price_data)
        portfolio = run_backtest(signal_data, initial_cash)
        value_history = portfolio.get_value_history_df()
        trade_log = portfolio.get_trade_log_df()

        total_return = calculate_total_return(value_history)
        max_dd = calculate_max_drawdown(value_history)
        sharpe = calculate_sharpe_ratio(value_history)
        bh_stats = calculate_buy_and_hold_return(price_data, initial_cash)

        # --- Metric cards ---
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(
            "Strategy Return",
            f"{total_return:.2f}%",
            delta=f"{total_return - bh_stats['total_return']:.2f} pts vs B&H",
        )
        col2.metric("Buy & Hold Return", f"{bh_stats['total_return']:.2f}%")
        col3.metric("Max Drawdown", f"{max_dd:.2f}%")
        col4.metric("Sharpe Ratio", f"{sharpe:.2f}")

        # --- Portfolio value over time: strategy vs buy & hold ---
        bh_curve = build_buy_and_hold_curve(price_data, initial_cash)

        value_fig = go.Figure()
        value_fig.add_trace(go.Scatter(
            x=value_history.index, y=value_history["total_value"],
            name="Strategy", line=dict(color="#2ca02c", width=2),
        ))
        value_fig.add_trace(go.Scatter(
            x=bh_curve.index, y=bh_curve.values,
            name="Buy & Hold", line=dict(color="#888888", width=2, dash="dash"),
        ))
        value_fig.update_layout(
            title=f"{ticker} — Portfolio Value Over Time",
            xaxis_title="Date", yaxis_title="Portfolio Value ($)",
            hovermode="x unified", height=400,
        )
        st.plotly_chart(value_fig, use_container_width=True)

        # --- Price chart with buy/sell markers ---
        price_fig = go.Figure()
        price_fig.add_trace(go.Scatter(
            x=price_data.index, y=price_data["Close"],
            name="Price", line=dict(color="#1f77b4", width=1.5),
        ))
        if not trade_log.empty:
            buys = trade_log[trade_log["action"] == "BUY"]
            sells = trade_log[trade_log["action"] == "SELL"]
            price_fig.add_trace(go.Scatter(
                x=buys["date"], y=buys["price"], mode="markers", name="Buy",
                marker=dict(color="green", symbol="triangle-up", size=11),
            ))
            price_fig.add_trace(go.Scatter(
                x=sells["date"], y=sells["price"], mode="markers", name="Sell",
                marker=dict(color="red", symbol="triangle-down", size=11),
            ))
        price_fig.update_layout(
            title=f"{ticker} — Price with Buy/Sell Signals",
            xaxis_title="Date", yaxis_title="Price ($)",
            hovermode="x unified", height=400,
        )
        st.plotly_chart(price_fig, use_container_width=True)

        with st.expander(f"{ticker} trade log ({len(trade_log)} trades)"):
            st.dataframe(trade_log, use_container_width=True)

        st.divider()