"""Deterministic synthetic transactions: ordinary customers plus planted suspicious patterns."""
from __future__ import annotations

import numpy as np
import pandas as pd

BENIGN_COUNTRIES = ["AM", "DE", "FR", "GE", "RU", "IT"]

# customer -> rule that must fire for the planted pattern
PLANTED = {
    "P_STRUCT": "structuring",
    "P_PASS": "rapid_movement",
    "P_RISKC": "high_risk_country",
    "P_SPIKE": "velocity_spike",
    "P_ROUND": "round_amounts",
    "P_CASH": "cash_threshold",
}


def generate(seed: int = 42, n_normal: int = 40, start: str = "2026-01-05", weeks: int = 13) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t0 = pd.Timestamp(start)
    rows: list[dict] = []

    def add(customer, ts, direction, amount, channel, country):
        rows.append({"customer_id": customer, "timestamp": ts, "direction": direction,
                     "amount": round(float(amount), 2), "channel": channel, "counterparty_country": country})

    def small_amount():
        return float(rng.integers(1000, 49000)) / 100.0 + 0.37  # 10.37 .. 490.37: never round

    for n in range(n_normal):
        customer = f"N{n:03d}"
        for _ in range(int(rng.integers(25, 45))):
            ts = t0 + pd.Timedelta(minutes=int(rng.integers(0, weeks * 7 * 24 * 60)))
            channel = str(rng.choice(["cash", "transfer", "card"], p=[0.2, 0.4, 0.4]))
            add(customer, ts, str(rng.choice(["in", "out"])), small_amount(), channel,
                str(rng.choice(BENIGN_COUNTRIES)))

    def background(customer, per_week=2, level=250.0):
        for w in range(weeks):
            for _ in range(per_week):
                ts = t0 + pd.Timedelta(weeks=w, hours=int(rng.integers(0, 24 * 6)))
                add(customer, ts, str(rng.choice(["in", "out"])), level + float(rng.integers(0, 5000)) / 100 + 0.11,
                    "transfer", "AM")

    d = t0 + pd.Timedelta(days=20)
    for i, amount in enumerate([9200.0, 9500.0, 9800.0, 9400.0]):          # structuring
        add("P_STRUCT", d + pd.Timedelta(days=i, hours=10), "in", amount, "cash", "AM")

    d = t0 + pd.Timedelta(days=30)                                          # pass-through
    add("P_PASS", d, "in", 20000.00, "transfer", "DE")
    add("P_PASS", d + pd.Timedelta(hours=10), "out", 19500.00, "transfer", "AE")

    d = t0 + pd.Timedelta(days=40)                                          # high-risk country
    add("P_RISKC", d, "out", 1800.00, "transfer", "IR")
    add("P_RISKC", d + pd.Timedelta(days=3), "out", 2200.00, "transfer", "IR")

    background("P_SPIKE")                                                   # velocity spike
    for k, amount in enumerate([4000.0, 3500.0, 4500.0]):
        add("P_SPIKE", t0 + pd.Timedelta(weeks=10, days=k, hours=9), "out", amount + 0.55, "transfer", "AM")

    d = t0 + pd.Timedelta(days=50)                                          # round amounts
    for i, amount in enumerate([2000, 3000, 2000, 5000, 3000]):
        add("P_ROUND", d + pd.Timedelta(days=i * 4), "out", amount, "transfer", "AM")

    add("P_CASH", t0 + pd.Timedelta(days=60), "in", 15000.00, "cash", "AM")  # single large cash

    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    df.insert(0, "txn_id", [f"T{n:06d}" for n in range(1, len(df) + 1)])
    return df
