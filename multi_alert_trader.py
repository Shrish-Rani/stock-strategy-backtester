"""
multi_alert_trader.py

Tracks EVERY strategy on EVERY ticker at once (not just whatever
config.STRATEGY happens to be set to), and emails you the instant
ANY of them buys or sells -- no matter which strategy triggered it.

Each (ticker, strategy) pair gets its OWN independent mini paper
portfolio, starting fresh with config.INITIAL_CASH. That means AAPL
tested with Moving Average and AAPL tested with RSI are tracked
completely separately, as if they were two different accounts --
this lets you directly compare how different strategies are doing
on the same stock, side by side, in real time.

When a SELL happens, the alert email shows the matching BUY price
from earlier, the SELL price, and whether that round-trip was a
profit or a loss -- a complete trade summary, not just a bare signal.

This does not replace paper_trader.py / alert_trader.py -- it's a
separate, additional system. Run it the same way (scheduled via
GitHub Actions, or manually with `python multi_alert_trader.py`).

Required environment variables (same as alert_trader.py):
    EMAIL_ADDRESS, EMAIL_APP_PASSWORD, ALERT_EMAIL_TO
"""

import json
import os
import smtplib
from email.mime.text import MIMEText
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

STATE_DIR = "multi_strategy_state"

# Every strategy this tracker checks. "ml" is intentionally excluded --
# it needs a train/test split, which doesn't fit a simple daily check.
ALL_STRATEGIES = [
    "moving_average", "rsi", "mean_reversion", "bollinger", "macd", "combined",
]

STRATEGY_DISPLAY_NAMES = {
    "moving_average": "Moving Average Crossover",
    "rsi": "RSI",
    "mean_reversion": "Mean Reversion",
    "bollinger": "Bollinger Bands",
    "macd": "MACD",
    "combined": "Combined (MA + RSI)",
}


def generate_signals_for(strategy_name: str, price_data):
    """Builds signals for one specific strategy, using the parameters
    already stored in config.py for that strategy (regardless of
    which one config.STRATEGY currently points to)."""
    if strategy_name == "moving_average":
        return moving_average_crossover_signals(price_data, config.SHORT_WINDOW, config.LONG_WINDOW)
    elif strategy_name == "rsi":
        return rsi_signals(price_data, config.RSI_PERIOD, config.RSI_OVERSOLD, config.RSI_OVERBOUGHT)
    elif strategy_name == "mean_reversion":
        return mean_reversion_signals(price_data, config.MEAN_REV_WINDOW, config.MEAN_REV_ENTRY_Z, config.MEAN_REV_EXIT_Z)
    elif strategy_name == "bollinger":
        return bollinger_band_signals(price_data, config.BOLLINGER_WINDOW, config.BOLLINGER_STD)
    elif strategy_name == "macd":
        return macd_signals(price_data, config.MACD_FAST, config.MACD_SLOW, config.MACD_SIGNAL)
    elif strategy_name == "combined":
        return combined_signal_strategy(
            price_data, config.SHORT_WINDOW, config.LONG_WINDOW,
            config.RSI_PERIOD, config.RSI_OVERSOLD, config.RSI_OVERBOUGHT,
        )
    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")


def send_email_alert(subject: str, body: str):
    sender = os.environ.get("EMAIL_ADDRESS")
    app_password = os.environ.get("EMAIL_APP_PASSWORD")
    recipient = os.environ.get("ALERT_EMAIL_TO", sender)

    if not sender or not app_password:
        print("Email credentials not set -- skipping email, printing alert instead:")
        print(subject)
        print(body)
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, app_password)
        server.sendmail(sender, recipient, msg.as_string())

    print(f"Alert email sent to {recipient}")


def state_file_path(ticker: str, strategy_name: str) -> str:
    return os.path.join(STATE_DIR, f"{ticker}_{strategy_name}.json")


def load_state(ticker: str, strategy_name: str, initial_cash: float) -> dict:
    path = state_file_path(ticker, strategy_name)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)

    return {
        "ticker": ticker,
        "strategy": strategy_name,
        "started_on": datetime.now().strftime("%Y-%m-%d"),
        "initial_cash": initial_cash,
        "cash": initial_cash,
        "shares": 0,
        "last_processed_date": None,
        "last_buy_price": None,
        "trade_log": [],
    }


def save_state(ticker: str, strategy_name: str, state: dict):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(state_file_path(ticker, strategy_name), "w") as f:
        json.dump(state, f, indent=2, default=str)


def check_ticker_strategy(ticker: str, strategy_name: str, initial_cash: float):
    display_name = STRATEGY_DISPLAY_NAMES[strategy_name]
    state = load_state(ticker, strategy_name, initial_cash)

    end = datetime.now()
    start = end - timedelta(days=400)
    price_data = load_price_data(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))

    signal_data = generate_signals_for(strategy_name, price_data)
    latest = signal_data.iloc[-1]
    latest_date = str(signal_data.index[-1].date())
    latest_price = float(latest["Close"])

    desired_holding = int(latest["signal"]) == 1
    currently_holding = state["shares"] > 0

    if state["last_processed_date"] == latest_date:
        return  # already checked today, nothing new to do

    if desired_holding and not currently_holding:
        shares_to_buy = int(state["cash"] // latest_price)
        if shares_to_buy > 0:
            cost = shares_to_buy * latest_price
            state["cash"] -= cost
            state["shares"] += shares_to_buy
            state["last_buy_price"] = latest_price
            state["trade_log"].append({
                "date": latest_date, "action": "BUY",
                "price": latest_price, "shares": shares_to_buy,
            })

            subject = f"[BUY] {ticker} -- {display_name}"
            body = (
                f"Strategy: {display_name}\n"
                f"Ticker: {ticker}\n"
                f"Action: BUY {shares_to_buy} shares at ${latest_price:.2f}\n"
                f"Date: {latest_date}\n"
            )
            send_email_alert(subject, body)
            print(f"{ticker} [{strategy_name}] BUY {shares_to_buy} @ ${latest_price:.2f}")

    elif not desired_holding and currently_holding:
        shares_sold = state["shares"]
        buy_price = state.get("last_buy_price")
        proceeds = shares_sold * latest_price
        state["cash"] += proceeds
        state["shares"] = 0
        state["trade_log"].append({
            "date": latest_date, "action": "SELL",
            "price": latest_price, "shares": shares_sold,
        })

        if buy_price:
            profit_dollars = (latest_price - buy_price) * shares_sold
            profit_percent = (latest_price - buy_price) / buy_price * 100
            result_word = "PROFIT" if profit_dollars >= 0 else "LOSS"
            trade_summary = (
                f"Bought at: ${buy_price:.2f}\n"
                f"Sold at:   ${latest_price:.2f}\n"
                f"Result:    {result_word} of ${abs(profit_dollars):.2f} "
                f"({profit_percent:+.2f}%)\n"
            )
        else:
            trade_summary = "(No matching buy price on record.)\n"

        subject = f"[SELL] {ticker} -- {display_name}"
        body = (
            f"Strategy: {display_name}\n"
            f"Ticker: {ticker}\n"
            f"Action: SELL {shares_sold} shares at ${latest_price:.2f}\n"
            f"Date: {latest_date}\n\n"
            f"{trade_summary}"
        )
        send_email_alert(subject, body)
        print(f"{ticker} [{strategy_name}] SELL {shares_sold} @ ${latest_price:.2f}")

    state["last_processed_date"] = latest_date
    save_state(ticker, strategy_name, state)


def main():
    tickers = getattr(config, "PAPER_TICKERS", getattr(config, "TICKERS", [config.TICKER]))
    print(f"Multi-strategy alert check -- tickers: {', '.join(tickers)}")
    print(f"Strategies tracked: {', '.join(ALL_STRATEGIES)}\n")

    for ticker in tickers:
        for strategy_name in ALL_STRATEGIES:
            try:
                check_ticker_strategy(ticker, strategy_name, config.INITIAL_CASH)
            except Exception as e:
                print(f"Could not check {ticker} [{strategy_name}]: {e}")


if __name__ == "__main__":
    main()
