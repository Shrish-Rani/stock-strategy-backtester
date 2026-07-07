"""
alert_trader.py

Same job as paper_trader.py -- checks real prices, decides if today's
signal says buy/sell/hold, updates the saved state -- but adds one
thing: it emails you whenever a real BUY or SELL happens.

This is the file meant to run automatically on a schedule (via GitHub
Actions, see the workflow file), not something you run by hand every
day. It reads your email credentials from environment variables
instead of hardcoding them in the file, so they can be stored as
GitHub Secrets and never appear in your actual code.

Required environment variables:
    EMAIL_ADDRESS       -- the Gmail address sending the alert
    EMAIL_APP_PASSWORD  -- a Gmail "app password" (NOT your normal password)
    ALERT_EMAIL_TO      -- where the alert should be sent (can be the same address)
"""

import os
import smtplib
from email.mime.text import MIMEText

import config
from paper_trader import (
    load_state,
    save_state,
    generate_signals,
)
from data_loader import load_price_data
from datetime import datetime, timedelta


def send_email_alert(subject: str, body: str):
    """Sends a plain-text email using Gmail's SMTP server. Requires
    EMAIL_ADDRESS and EMAIL_APP_PASSWORD to be set as environment
    variables (GitHub Secrets when run via Actions)."""
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


def check_ticker_with_alert(ticker: str, initial_cash: float):
    print(f"\n--- {ticker} ---")
    state = load_state(ticker, initial_cash)

    end = datetime.now()
    start = end - timedelta(days=400)
    price_data = load_price_data(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))

    signal_data = generate_signals(price_data)
    latest = signal_data.iloc[-1]
    latest_date = str(signal_data.index[-1].date())
    latest_price = float(latest["Close"])

    desired_holding = int(latest["signal"]) == 1
    currently_holding = state["shares"] > 0

    action_taken = None

    if state["last_processed_date"] == latest_date:
        print(f"Already checked {latest_date}. No new action.")
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
                action_taken = f"BUY {shares_to_buy} shares of {ticker} at ${latest_price:.2f}"
                print(action_taken)
        elif not desired_holding and currently_holding:
            proceeds = state["shares"] * latest_price
            action_taken = f"SELL {state['shares']} shares of {ticker} at ${latest_price:.2f}"
            print(action_taken)
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

    print(f"Total value: ${total_value:.2f}  ({total_return:.2f}% since {state['started_on']})")
    save_state(ticker, state)

    if action_taken:
        subject = f"[Stock Alert] {ticker}: {action_taken.split(' ')[0]} signal"
        body = (
            f"{action_taken}\n\n"
            f"Strategy: {config.STRATEGY}\n"
            f"Date: {latest_date}\n"
            f"Current portfolio value: ${total_value:.2f}\n"
            f"Return so far: {total_return:.2f}% (tracking since {state['started_on']})\n"
        )
        send_email_alert(subject, body)


def main():
    tickers = getattr(config, "PAPER_TICKERS", getattr(config, "TICKERS", [config.TICKER]))
    print(f"Alert check -- strategy: {config.STRATEGY}")
    print(f"Tickers: {', '.join(tickers)}")

    for ticker in tickers:
        try:
            check_ticker_with_alert(ticker, config.INITIAL_CASH)
        except Exception as e:
            print(f"Could not check {ticker}: {e}")


if __name__ == "__main__":
    main()
