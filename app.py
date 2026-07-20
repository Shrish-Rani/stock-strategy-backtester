"""
app.py

An interactive web dashboard for the backtester, built with Streamlit.

Run it with:
    streamlit run app.py

Two analysis modes:
  - Per-Ticker: test each ticker independently, its own full cash amount
  - Portfolio: split cash across all tickers together and see the
    COMBINED result (this is where diversification effects show up)

Visual design: a disciplined "systematic trading terminal" look --
deep ink-navy background, a muted brass accent (a nod to old ticker-
tape boards), and monospaced numerals for every price/percentage,
the same way real trading terminals visually separate data from
chrome. Green/red are reserved strictly for actual gains/losses.
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
from risk_management import apply_stop_loss_take_profit
from backtester import run_backtest
from portfolio_backtest import run_portfolio_backtest
from metrics import (
    calculate_total_return,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_buy_and_hold_return,
)

# ---------------- Design tokens ----------------
BG_PRIMARY = "#0B0E14"
BG_SECONDARY = "#141925"
BG_TERTIARY = "#1C2333"
BORDER = "#2A3142"
TEXT_PRIMARY = "#E8EAF0"
TEXT_SECONDARY = "#8B92A8"
TEXT_TERTIARY = "#5A6178"
ACCENT_BRASS = "#C9A227"
ACCENT_TEAL = "#4FD1C5"
POSITIVE = "#3FB68C"
NEGATIVE = "#E5484D"

FONT_DISPLAY = "'Space Grotesk', sans-serif"
FONT_BODY = "'Inter', sans-serif"
FONT_MONO = "'IBM Plex Mono', monospace"


@st.cache_data
def get_price_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    return load_price_data(ticker, start, end)


st.set_page_config(page_title="Strategy Terminal", layout="wide", page_icon="◆")

# ---------------- Global styling ----------------
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
    font-family: {FONT_BODY};
}}
h1, h2, h3 {{
    font-family: {FONT_DISPLAY} !important;
    letter-spacing: -0.01em;
}}

/* Sidebar section headers styled as small letter-spaced eyebrows */
section[data-testid="stSidebar"] {{
    background-color: {BG_SECONDARY};
    border-right: 1px solid {BORDER};
}}
section[data-testid="stSidebar"] h2 {{
    font-family: {FONT_BODY} !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: {ACCENT_BRASS} !important;
    margin-top: 1.4rem;
    margin-bottom: 0.4rem;
}}
section[data-testid="stSidebar"] h3 {{
    font-family: {FONT_BODY} !important;
    font-size: 0.68rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: {TEXT_SECONDARY} !important;
    margin-top: 1rem;
}}

/* Masthead */
.masthead-eyebrow {{
    font-family: {FONT_BODY};
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: {ACCENT_BRASS};
    margin-bottom: 0.3rem;
}}
.masthead-title {{
    font-family: {FONT_DISPLAY};
    font-size: 2.1rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    margin: 0;
}}
.masthead-sub {{
    font-family: {FONT_BODY};
    font-size: 0.92rem;
    color: {TEXT_SECONDARY};
    margin-top: 0.35rem;
}}
.masthead-rule {{
    height: 1px;
    background: linear-gradient(90deg, {ACCENT_BRASS} 0%, {BORDER} 45%, transparent 100%);
    margin: 1.1rem 0 1.6rem 0;
}}

/* Metric cards */
.metric-row {{
    display: flex;
    gap: 0.9rem;
    margin-bottom: 1.4rem;
    flex-wrap: wrap;
}}
.metric-card {{
    flex: 1;
    min-width: 160px;
    background: {BG_SECONDARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 0.9rem 1.1rem;
}}
.metric-label {{
    font-family: {FONT_BODY};
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {TEXT_SECONDARY};
    margin-bottom: 0.35rem;
}}
.metric-value {{
    font-family: {FONT_MONO};
    font-size: 1.5rem;
    font-weight: 600;
    color: {TEXT_PRIMARY};
}}
.metric-value.positive {{ color: {POSITIVE}; }}
.metric-value.negative {{ color: {NEGATIVE}; }}
.metric-delta {{
    font-family: {FONT_MONO};
    font-size: 0.78rem;
    margin-top: 0.25rem;
}}
.metric-delta.positive {{ color: {POSITIVE}; }}
.metric-delta.negative {{ color: {NEGATIVE}; }}

/* Section labels used inline in the main area */
.section-eyebrow {{
    font-family: {FONT_BODY};
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: {ACCENT_BRASS};
    margin-top: 1.6rem;
    margin-bottom: 0.2rem;
}}
.ticker-name {{
    font-family: {FONT_DISPLAY};
    font-size: 1.5rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}

/* Buttons */
.stButton button, .stButton button:focus {{
    font-family: {FONT_BODY};
    font-weight: 600;
    letter-spacing: 0.02em;
    border-radius: 6px;
}}

/* Divider */
hr {{
    border-color: {BORDER} !important;
}}
</style>
""", unsafe_allow_html=True)


def render_masthead():
    st.markdown(f"""
    <div class="masthead-eyebrow">Systematic Strategy Terminal</div>
    <div class="masthead-title">Stock Strategy Backtester</div>
    <div class="masthead-sub">Historical simulation &amp; live paper-trading research console</div>
    <div class="masthead-rule"></div>
    """, unsafe_allow_html=True)


def render_metric_row(cards: list):
    """cards: list of dicts with keys label, value, and optionally
    sentiment ('positive' | 'negative' | 'neutral') and delta (string).

    Builds the whole row as ONE continuous line of HTML, with no
    internal blank lines. This matters because Streamlit's markdown
    parser ends a raw HTML block the moment it hits a blank line --
    if a card has no delta, leaving an empty placeholder line would
    silently break the rest of the row and dump raw HTML as text."""
    parts = ['<div class="metric-row">']
    for c in cards:
        sentiment = c.get("sentiment", "neutral")
        value_class = f"metric-value {sentiment}" if sentiment != "neutral" else "metric-value"
        delta_html = ""
        if c.get("delta"):
            delta_class = f"metric-delta {sentiment}" if sentiment != "neutral" else "metric-delta"
            delta_html = f'<div class="{delta_class}">{c["delta"]}</div>'
        parts.append(
            '<div class="metric-card">'
            f'<div class="metric-label">{c["label"]}</div>'
            f'<div class="{value_class}">{c["value"]}</div>'
            f'{delta_html}'
            '</div>'
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def _sentiment(value: float) -> str:
    return "positive" if value >= 0 else "negative"


render_masthead()

# ---------------- Sidebar: all user controls live here ----------------
st.sidebar.header("Universe")

default_tickers = ", ".join(getattr(config, "TICKERS", [config.TICKER]))
tickers_input = st.sidebar.text_input("Tickers (comma-separated)", value=default_tickers)
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

analysis_mode = st.sidebar.radio(
    "Analysis mode",
    ["Per-Ticker (each stock tested alone)", "Portfolio (combined across tickers)"],
)

st.sidebar.header("Strategy")
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
    label_visibility="collapsed",
)

start_date = st.sidebar.date_input("Start date", pd.to_datetime(config.START_DATE).date())
end_date = st.sidebar.date_input("End date", pd.to_datetime(config.get_current_date()).date())
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

st.sidebar.header("Risk Management")
use_stop_loss = st.sidebar.checkbox("Apply stop-loss / take-profit")
if use_stop_loss:
    stop_loss_pct = st.sidebar.slider("Stop-loss (%)", -30, -1, -8)
    take_profit_pct = st.sidebar.slider("Take-profit (%)", 1, 50, 15)
    st.sidebar.caption(
        "Forces an exit if a position moves against you past the stop-loss, "
        "or in your favor past the take-profit -- even if the strategy's "
        "own signal hasn't reversed yet."
    )

run_clicked = st.sidebar.button("Run Backtest", type="primary", use_container_width=True)


def generate_signals(price_data: pd.DataFrame) -> pd.DataFrame:
    """Routes to whichever strategy the user picked in the sidebar,
    then optionally applies a stop-loss/take-profit overlay on top."""
    if strategy_name == "Moving Average Crossover":
        signals = moving_average_crossover_signals(price_data, short_window, long_window)
    elif strategy_name == "RSI":
        signals = rsi_signals(price_data, rsi_period, oversold, overbought)
    elif strategy_name == "Mean Reversion":
        signals = mean_reversion_signals(price_data, mr_window, entry_z, exit_z)
    elif strategy_name == "Bollinger Bands":
        signals = bollinger_band_signals(price_data, bb_window, bb_std)
    elif strategy_name == "MACD":
        signals = macd_signals(price_data, macd_fast, macd_slow, macd_signal_period)
    elif strategy_name == "Combined (MA + RSI)":
        signals = combined_signal_strategy(
            price_data, c_short, c_long, c_rsi_period, c_oversold, c_overbought
        )
    else:  # Machine Learning
        signals = generate_ml_signals(price_data, ml_test_size)

    if use_stop_loss:
        signals = apply_stop_loss_take_profit(signals, stop_loss_pct, take_profit_pct)

    return signals


def build_buy_and_hold_curve(price_data: pd.DataFrame, cash: float) -> pd.Series:
    start_price = price_data["Close"].iloc[0]
    shares = int(cash // start_price)
    leftover_cash = cash - (shares * start_price)
    return leftover_cash + shares * price_data["Close"]


def _base_layout(fig, title):
    fig.update_layout(
        title=dict(text=title, font=dict(family=FONT_DISPLAY, size=16, color=TEXT_PRIMARY)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_BODY, color=TEXT_SECONDARY, size=12),
        xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, tickfont=dict(family=FONT_MONO)),
        yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, tickfont=dict(family=FONT_MONO)),
        hoverlabel=dict(bgcolor=BG_TERTIARY, font_family=FONT_MONO, font_size=12,
                         bordercolor=BORDER),
        legend=dict(font=dict(family=FONT_BODY, size=11)),
        height=400,
    )
    return fig


def render_value_chart(ticker, value_history, bh_curve, signal_data=None):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=value_history.index, y=value_history["total_value"],
        name="Strategy", line=dict(color=ACCENT_TEAL, width=2),
    ))
    fig.add_trace(go.Scatter(
        x=bh_curve.index, y=bh_curve.values,
        name="Buy & Hold", line=dict(color=TEXT_TERTIARY, width=2, dash="dash"),
    ))
    if signal_data is not None and "is_test_period" in signal_data.columns:
        test_start = signal_data[signal_data["is_test_period"]].index.min()
        if pd.notna(test_start):
            fig.add_vline(x=test_start, line_dash="dot", line_color=ACCENT_BRASS)
            fig.add_annotation(x=test_start, y=1, yref="paper", showarrow=False,
                                text="Test period begins", bgcolor=ACCENT_BRASS,
                                font=dict(color=BG_PRIMARY, family=FONT_BODY, size=11))
    _base_layout(fig, f"{ticker} — Portfolio Value Over Time")
    fig.update_layout(xaxis_title="Date", yaxis_title="Portfolio Value ($)", hovermode="x unified")
    return fig


def _format_trade_pair_hovertext(buys, sells):
    """
    Builds custom hover text for each Buy/Sell marker that shows its
    ACTUAL paired trade -- not just whatever happens to be nearest on
    the timeline. Trades alternate BUY, SELL, BUY, SELL... (our
    backtester is always fully in or fully out), so the i-th buy is
    always paired with the i-th sell, if one exists yet.

    Returns (buy_hover_texts, sell_hover_texts) -- lists of strings,
    one per marker, in the same order as the buys/sells DataFrames.
    """
    buy_texts = []
    for i in range(len(buys)):
        buy_row = buys.iloc[i]
        buy_date = pd.to_datetime(buy_row["date"]).date()
        text = f"BUY: {buy_date} @ ${buy_row['price']:.2f}"

        if i < len(sells):
            sell_row = sells.iloc[i]
            sell_date = pd.to_datetime(sell_row["date"]).date()
            profit = (sell_row["price"] - buy_row["price"]) * buy_row["shares"]
            pct = (sell_row["price"] - buy_row["price"]) / buy_row["price"] * 100
            word = "Profit" if profit >= 0 else "Loss"
            text += (f"<br>Later SOLD: {sell_date} @ ${sell_row['price']:.2f}"
                     f"<br>{word}: ${abs(profit):.2f} ({pct:+.2f}%)")
        else:
            text += "<br>(Still holding -- not sold yet)"
        buy_texts.append(text)

    sell_texts = []
    for i in range(len(sells)):
        sell_row = sells.iloc[i]
        sell_date = pd.to_datetime(sell_row["date"]).date()
        text = f"SELL: {sell_date} @ ${sell_row['price']:.2f}"

        if i < len(buys):
            buy_row = buys.iloc[i]
            buy_date = pd.to_datetime(buy_row["date"]).date()
            profit = (sell_row["price"] - buy_row["price"]) * sell_row["shares"]
            pct = (sell_row["price"] - buy_row["price"]) / buy_row["price"] * 100
            word = "Profit" if profit >= 0 else "Loss"
            text += (f"<br>Bought at: {buy_date} @ ${buy_row['price']:.2f}"
                      f"<br>{word}: ${abs(profit):.2f} ({pct:+.2f}%)")
        sell_texts.append(text)

    return buy_texts, sell_texts


def render_price_chart(ticker, price_data, trade_log, signal_data=None):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=price_data.index, y=price_data["Close"],
        name="Price", line=dict(color=TEXT_PRIMARY, width=1.5),
    ))
    if not trade_log.empty:
        buys = trade_log[trade_log["action"] == "BUY"].reset_index(drop=True)
        sells = trade_log[trade_log["action"] == "SELL"].reset_index(drop=True)
        buy_hover, sell_hover = _format_trade_pair_hovertext(buys, sells)

        fig.add_trace(go.Scatter(
            x=buys["date"], y=buys["price"], mode="markers", name="Buy",
            marker=dict(color=POSITIVE, symbol="triangle-up", size=11,
                        line=dict(color=BG_PRIMARY, width=1)),
            text=buy_hover, hoverinfo="text",
        ))
        fig.add_trace(go.Scatter(
            x=sells["date"], y=sells["price"], mode="markers", name="Sell",
            marker=dict(color=NEGATIVE, symbol="triangle-down", size=11,
                        line=dict(color=BG_PRIMARY, width=1)),
            text=sell_hover, hoverinfo="text",
        ))
    if signal_data is not None and "is_test_period" in signal_data.columns:
        test_start = signal_data[signal_data["is_test_period"]].index.min()
        if pd.notna(test_start):
            fig.add_vline(x=test_start, line_dash="dot", line_color=ACCENT_BRASS)
    _base_layout(fig, f"{ticker} — Price with Buy/Sell Signals")
    fig.update_layout(xaxis_title="Date", yaxis_title="Price ($)", hovermode="closest")
    return fig


# ---------------- Main area ----------------
if not run_clicked:
    st.info("Set your tickers and strategy in the sidebar, then click **Run Backtest**.")
elif not tickers:
    st.error("Enter at least one ticker symbol.")

elif analysis_mode.startswith("Per-Ticker"):
    for ticker in tickers:
        st.markdown(f'<div class="ticker-name">{ticker}</div>', unsafe_allow_html=True)
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
        vs_bh = total_return - bh_stats["total_return"]

        render_metric_row([
            {"label": "Strategy Return", "value": f"{total_return:.2f}%",
             "sentiment": _sentiment(total_return),
             "delta": f"{vs_bh:+.2f} pts vs B&H"},
            {"label": "Buy & Hold Return", "value": f"{bh_stats['total_return']:.2f}%",
             "sentiment": _sentiment(bh_stats["total_return"])},
            {"label": "Max Drawdown", "value": f"{max_dd:.2f}%", "sentiment": "negative"},
            {"label": "Sharpe Ratio", "value": f"{sharpe:.2f}", "sentiment": _sentiment(sharpe)},
        ])

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
    st.markdown(
        f'<div class="ticker-name">Combined Portfolio — {", ".join(tickers)}</div>',
        unsafe_allow_html=True,
    )

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

    render_metric_row([
        {"label": "Combined Portfolio Return", "value": f"{total_return:.2f}%",
         "sentiment": _sentiment(total_return)},
        {"label": "Combined Max Drawdown", "value": f"{max_dd:.2f}%", "sentiment": "negative"},
        {"label": "Combined Sharpe Ratio", "value": f"{sharpe:.2f}", "sentiment": _sentiment(sharpe)},
    ])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=combined.index, y=combined["total_value"],
        name="Combined Portfolio", line=dict(color=ACCENT_TEAL, width=2),
    ))
    _base_layout(fig, "Combined Portfolio Value Over Time")
    fig.update_layout(xaxis_title="Date", yaxis_title="Portfolio Value ($)",
                       hovermode="x unified", height=450)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-eyebrow">How Each Ticker Contributed</div>',
                unsafe_allow_html=True)
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