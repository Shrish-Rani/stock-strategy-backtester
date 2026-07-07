"""
portfolio.py

A simple object that tracks:
  - how much cash we have
  - how many shares we own
  - a log of every trade we made
  - the total value of the portfolio over time (cash + shares * price)

Think of this as your fake brokerage account.
"""

import pandas as pd


class Portfolio:
    def __init__(self, initial_cash: float):
        self.cash = initial_cash
        self.shares = 0
        self.trade_log = []       # list of dicts: {date, action, price, shares}
        self.value_history = []   # list of dicts: {date, total_value}

    def buy(self, date, price: float):
        """Spend all available cash to buy as many whole shares as possible."""
        if self.cash <= 0:
            return
        shares_to_buy = int(self.cash // price)
        if shares_to_buy == 0:
            return

        cost = shares_to_buy * price
        self.cash -= cost
        self.shares += shares_to_buy

        self.trade_log.append({
            "date": date,
            "action": "BUY",
            "price": price,
            "shares": shares_to_buy,
        })

    def sell(self, date, price: float):
        """Sell every share we currently hold."""
        if self.shares <= 0:
            return

        proceeds = self.shares * price
        self.cash += proceeds

        self.trade_log.append({
            "date": date,
            "action": "SELL",
            "price": price,
            "shares": self.shares,
        })
        self.shares = 0

    def record_value(self, date, current_price: float):
        """Log the total portfolio value (cash + stock holdings) for this day."""
        total_value = self.cash + (self.shares * current_price)
        self.value_history.append({"date": date, "total_value": total_value})

    def get_value_history_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.value_history).set_index("date")

    def get_trade_log_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.trade_log)
