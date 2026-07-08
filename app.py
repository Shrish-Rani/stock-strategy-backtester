"""
app.py

An interactive web dashboard for the backtester, built with Streamlit.

Run it with:
    streamlit run app.py

Two analysis modes:
  - Per-Ticker: test each ticker independently, its own full cash amount
  - Portfolio: split cash across all tickers together and see the
    COMBINED result (this is where diversification effects show up)
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
    bollinger_band_signals,
    macd_signals,
    combined_signal_strategy,
)
from ml_strategy import generate_ml_signals
from backtester import run_backtest
from portfolio_backtest import run_portfolio_backtest
from metrics import (
    calculate_total_return,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_buy_and_hold_return,
)


@st.cache_data
def get_price_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    return load_price_data(ticker, start, end)


st.set_page_config(page_title="Strategy Backtester", layout="wide")
st.title("Stock Strategy Backtester")

# ---------------- Sidebar: all user controls live here ----------------
st.sidebar.header("Settings")

default_tickers = ", ".join(getattr(config, "TICKERS", [config.TICKER]))
tickers_input = st.sidebar.text_input("Tickers (comma-separated)", value=default_tickers)
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

analysis_mode = st.sidebar.radio(
    "Analysis mode",
    ["Per-Ticker (each stock tested alone)", "Portfolio (combined across tickers)"],
)

strategy_name = st.sidebar.selectbox(
    "Strategy",
    [
        "Moving Average Crossover",
        "RSI",
        "Mean Reversion",
        "Bollinger Bands",
        "MACD",
        "Combined (MA + RSI)",
        "Machine Learning (Random Forest)",
    ],
)

start_date = st.sidebar.date_input("Start date", pd.to_datetime(config.START_DATE).date())
end_date = st.sidebar.date_input("End date", pd.to_datetime(config.END_DATE).date())
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
elif strategy_name == "Mean Reversion":
    mr_window = st.sidebar.slider("Rolling window (days)", 5, 60, config.MEAN_REV_WINDOW)
    entry_z = st.sidebar.slider("Entry z-score", 0.5, 3.0, config.MEAN_REV_ENTRY_Z, step=0.1)
    exit_z = st.sidebar.slider("Exit z-score", -1.0, 1.0, config.MEAN_REV_EXIT_Z, step=0.1)
elif strategy_name == "Bollinger Bands":
    bb_window = st.sidebar.slider("Rolling window (days)", 5, 60, config.BOLLINGER_WINDOW)
    bb_std = st.sidebar.slider("Band width (std devs)", 1.0, 3.5, config.BOLLINGER_STD, step=0.1)
elif strategy_name == "MACD":
    macd_fast = st.sidebar.slider("Fast EMA period", 5, 20, config.MACD_FAST)
    macd_slow = st.sidebar.slider("Slow EMA period", 15, 50, config.MACD_SLOW)
    macd_signal_period = st.sidebar.slider("Signal line period", 5, 20, config.MACD_SIGNAL)
elif strategy_name == "Combined (MA + RSI)":
    c_short = st.sidebar.slider("MA short window", 5, 60, config.SHORT_WINDOW)
    c_long = st.sidebar.slider("MA long window", 20, 250, config.LONG_WINDOW)
    c_rsi_period = st.sidebar.slider("RSI period", 5, 30, config.RSI_PERIOD)
    c_oversold = st.sidebar.slider("RSI oversold", 10, 40, config.RSI_OVERSOLD)
    c_overbought = st.sidebar.slider("RSI overbought", 60, 90, config.RSI_OVERBOUGHT)
else:  # Machine Learning
    ml_test_size = st.sidebar.slider(
        "Test period size (fraction held out)", 0.1, 0.5, config.ML_TEST_SIZE, step=0.05
    )
    st.sidebar.caption(
        "The model trains on the earlier portion of your date range and is "
        "only backtested on the later, unseen portion -- see the chart "
        "below for exactly where that split happens."
    )

run_clicked = st.sidebar.button("Run Backtest", type="primary")


def generate_signals(price_data: pd.DataFrame) -> pd.DataFrame:
    """Routes to whichever strategy the user picked in the sidebar."""
    if strategy_name == "Moving Average Crossover":
        return moving_average_crossover_signals(price_data, short_window, long_window)
    elif strategy_name == "RSI":
        return rsi_signals(price_data, rsi_period, oversold, overbought)
    elif strategy_name == "Mean Reversion":
        return mean_reversion_signals(price_data, mr_window, entry_z, exit_z)
    elif strategy_name == "Bollinger Bands":
        return bollinger_band_signals(price_data, bb_window, bb_std)
    elif strategy_name == "MACD":
        return macd_signals(price_data, macd_fast, macd_slow, macd_signal_period)
    elif strategy_name == "Combined (MA + RSI)":
        return combined_signal_strategy(
            price_data, c_short, c_long, c_rsi_period, c_oversold, c_overbought
        )
    else:  # Machine Learning
        return generate_ml_signals(price_data, ml_test_size)


def build_buy_and_hold_curve(price_data: pd.DataFrame, cash: float) -> pd.Series:
    start_price = price_data["Close"].iloc[0]
    shares = int(cash // start_price)
    leftover_cash = cash - (shares * start_price)
    return leftover_cash + shares * price_data["Close"]


def render_value_chart(ticker, value_history, bh_curve, signal_data=None):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=value_history.index, y=value_history["total_value"],
        name="Strategy", line=dict(color="#2ca02c", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=bh_curve.index, y=bh_curve.values,
        name="Buy & Hold", line=dict(color="#888888", width=2, dash="dash"),
    ))
    if signal_data is not None and "is_test_period" in signal_data.columns:
        test_start = signal_data[signal_data["is_test_period"]].index.min()
        if pd.notna(test_start):
            fig.add_vline(x=test_start, line_dash="dot", line_color="orange")
            fig.add_annotation(x=test_start, y=1, yref="paper", showarrow=False,
                                text="Test period begins", bgcolor="orange")
    fig.update_layout(
        title=f"{ticker} — Portfolio Value Over Time",
        xaxis_title="Date", yaxis_title="Portfolio Value ($)",
        hovermode="x unified", height=400,
    )
    return fig


def render_price_chart(ticker, price_data, trade_log, signal_data=None):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=price_data.index, y=price_data["Close"],
        name="Price", line=dict(color="#1f77b4", width=1.5),
    ))
    if not trade_log.empty:
        buys = trade_log[trade_log["action"] == "BUY"]
        sells = trade_log[trade_log["action"] == "SELL"]
        fig.add_trace(go.Scatter(
            x=buys["date"], y=buys["price"], mode="markers", name="Buy",
            marker=dict(color="green", symbol="triangle-up", size=11),
        ))
        fig.add_trace(go.Scatter(
            x=sells["date"], y=sells["price"], mode="markers", name="Sell",
            marker=dict(color="red", symbol="triangle-down", size=11),
        ))
    if signal_data is not None and "is_test_period" in signal_data.columns:
        test_start = signal_data[signal_data["is_test_period"]].index.min()
        if pd.notna(test_start):
            fig.add_vline(x=test_start, line_dash="dot", line_color="orange")
    fig.update_layout(
        title=f"{ticker} — Price with Buy/Sell Signals",
        xaxis_title="Date", yaxis_title="Price ($)",
        hovermode="x unified", height=400,
    )
    return fig


# ---------------- Main area ----------------
if not run_clicked:
    st.info("Set your tickers and strategy in the sidebar, then click **Run Backtest**.")
elif not tickers:
    st.error("Enter at least one ticker symbol.")

elif analysis_mode.startswith("Per-Ticker"):
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

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Strategy Return", f"{total_return:.2f}%",
                     delta=f"{total_return - bh_stats['total_return']:.2f} pts vs B&H")
        col2.metric("Buy & Hold Return", f"{bh_stats['total_return']:.2f}%")
        col3.metric("Max Drawdown", f"{max_dd:.2f}%")
        col4.metric("Sharpe Ratio", f"{sharpe:.2f}")

        bh_curve = build_buy_and_hold_curve(price_data, initial_cash)
        st.plotly_chart(
            render_value_chart(ticker, value_history, bh_curve, signal_data),
            use_container_width=True,
        )
        st.plotly_chart(
            render_price_chart(ticker, price_data, trade_log, signal_data),
            use_container_width=True,
        )

        with st.expander(f"{ticker} trade log ({len(trade_log)} trades)"):
            st.dataframe(trade_log, use_container_width=True)

        st.divider()

else:  # Portfolio mode
    st.header(f"Combined Portfolio — {', '.join(tickers)}")

    try:
        result = run_portfolio_backtest(
            tickers, generate_signals, str(start_date), str(end_date), initial_cash
        )
    except Exception as e:
        st.error(f"Could not run portfolio backtest: {e}")
        st.stop()

    combined = result["combined_value_history"]
    total_return = calculate_total_return(combined)
    max_dd = calculate_max_drawdown(combined)
    sharpe = calculate_sharpe_ratio(combined)

    col1, col2, col3 = st.columns(3)
    col1.metric("Combined Portfolio Return", f"{total_return:.2f}%")
    col2.metric("Combined Max Drawdown", f"{max_dd:.2f}%")
    col3.metric("Combined Sharpe Ratio", f"{sharpe:.2f}")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=combined.index, y=combined["total_value"],
        name="Combined Portfolio", line=dict(color="#2ca02c", width=2),
    ))
    fig.update_layout(
        title="Combined Portfolio Value Over Time",
        xaxis_title="Date", yaxis_title="Portfolio Value ($)",
        hovermode="x unified", height=450,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("How each ticker contributed")
    breakdown_rows = []
    for ticker, r in result["per_ticker"].items():
        vh = r["value_history"]
        breakdown_rows.append({
            "Ticker": ticker,
            "Individual Return": f"{calculate_total_return(vh):.2f}%",
            "Individual Max Drawdown": f"{calculate_max_drawdown(vh):.2f}%",
            "Trades": len(r["trade_log"]),
        })
    st.dataframe(pd.DataFrame(breakdown_rows), use_container_width=True)

    st.caption(
        "Notice the combined portfolio's max drawdown is often smaller than "
        "any single ticker's -- that's diversification in action. When one "
        "stock is down, another may be flat or up, smoothing the ride."
    )