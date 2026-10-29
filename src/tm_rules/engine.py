"""Rule engine. Every rule returns alerts with a human-readable reason."""
from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Callable

import pandas as pd
import yaml

ALERT_COLUMNS = ["alert_id", "rule_id", "severity", "customer_id", "txn_count", "total_amount",
                 "window_start", "window_end", "txn_ids", "description"]
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def default_config_path() -> Path:
    return Path(str(resources.files("tm_rules").joinpath("rules.yaml")))


def load_rules(path: str | Path | None = None) -> dict:
    with open(path or default_config_path(), encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    if not isinstance(config, dict) or "rules" not in config:
        raise ValueError("Rules file must contain a top-level 'rules' mapping")
    return config["rules"]


def _alert(rule_id: str, severity: str, customer_id: str, group: pd.DataFrame, description: str) -> dict:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "customer_id": customer_id,
        "txn_count": len(group),
        "total_amount": round(float(group["amount"].sum()), 2),
        "window_start": group["timestamp"].min(),
        "window_end": group["timestamp"].max(),
        "txn_ids": ";".join(group["txn_id"]),
        "description": description,
    }


def _greedy_windows(group: pd.DataFrame, window: pd.Timedelta, min_count: int, min_total: float):
    """Non-overlapping windows that start at a transaction and satisfy count/total limits."""
    group = group.sort_values("timestamp")
    times = group["timestamp"].tolist()
    i = 0
    while i < len(group):
        j = i
        while j + 1 < len(group) and times[j + 1] - times[i] <= window:
            j += 1
        chunk = group.iloc[i:j + 1]
        if len(chunk) >= min_count and chunk["amount"].sum() >= min_total:
            yield chunk
            i = j + 1
        else:
            i += 1


def cash_threshold(df: pd.DataFrame, p: dict) -> list[dict]:
    hits = df[(df["channel"] == "cash") & (df["amount"] >= p["threshold"])]
    return [
        _alert("cash_threshold", p["severity"], row.customer_id, hits.loc[[idx]],
               f"Cash {row.direction} of {row.amount:,.2f} on {row.timestamp:%Y-%m-%d}, at or above the "
               f"{p['threshold']:,.0f} threshold.")
        for idx, row in hits.iterrows()
    ]


def structuring(df: pd.DataFrame, p: dict) -> list[dict]:
    low = p["upper_threshold"] * p["lower_bound_ratio"]
    cash = df[(df["channel"] == "cash") & (df["amount"] < p["upper_threshold"]) & (df["amount"] >= low)]
    alerts = []
    window = pd.Timedelta(days=p["window_days"])
    for customer, grp in cash.groupby("customer_id"):
        for chunk in _greedy_windows(grp, window, p["min_txn_count"], p["min_total"]):
            alerts.append(_alert(
                "structuring", p["severity"], customer, chunk,
                f"{len(chunk)} cash transactions between {low:,.0f} and {p['upper_threshold']:,.0f} within "
                f"{p['window_days']} days, totalling {chunk['amount'].sum():,.2f}: possible structuring."))
    return alerts


def rapid_movement(df: pd.DataFrame, p: dict) -> list[dict]:
    alerts = []
    window = pd.Timedelta(hours=p["window_hours"])
    for customer, grp in df.groupby("customer_id"):
        inflows = grp[(grp["direction"] == "in") & (grp["amount"] >= p["min_inflow"])]
        outflows = grp[grp["direction"] == "out"]
        used: set[str] = set()
        for _, inflow in inflows.iterrows():
            later = outflows[(outflows["timestamp"] >= inflow["timestamp"]) &
                             (outflows["timestamp"] <= inflow["timestamp"] + window) &
                             (~outflows["txn_id"].isin(used))]
            if later["amount"].sum() >= p["passthrough_ratio"] * inflow["amount"]:
                used.update(later["txn_id"])
                members = pd.concat([grp[grp["txn_id"] == inflow["txn_id"]], later])
                alerts.append(_alert(
                    "rapid_movement", p["severity"], customer, members,
                    f"Inflow of {inflow['amount']:,.2f} followed by outflows of {later['amount'].sum():,.2f} "
                    f"within {p['window_hours']} hours: possible pass-through / layering."))
    return alerts


def high_risk_country(df: pd.DataFrame, p: dict) -> list[dict]:
    risky = df[df["counterparty_country"].isin(p["countries"]) & (df["amount"] >= p["min_amount"])]
    alerts = []
    for (customer, country), grp in risky.groupby(["customer_id", "counterparty_country"]):
        alerts.append(_alert(
            "high_risk_country", p["severity"], customer, grp,
            f"{len(grp)} transaction(s) totalling {grp['amount'].sum():,.2f} with counterparties in {country} "
            f"(high-risk jurisdiction list)."))
    return alerts


def velocity_spike(df: pd.DataFrame, p: dict) -> list[dict]:
    work = df.copy()
    work["week"] = work["timestamp"].dt.to_period("W")
    alerts = []
    for customer, grp in work.groupby("customer_id"):
        weekly = grp.groupby("week")["amount"].sum()
        weekly = weekly.reindex(pd.period_range(weekly.index.min(), weekly.index.max(), freq="W"), fill_value=0.0)
        for pos in range(p["min_history_weeks"], len(weekly)):
            history = weekly.iloc[max(0, pos - p["baseline_weeks"]):pos]
            baseline = history.mean()
            current = weekly.iloc[pos]
            if current >= p["min_amount"] and current >= p["multiplier"] * max(baseline, 1.0):
                members = grp[grp["week"] == weekly.index[pos]]
                alerts.append(_alert(
                    "velocity_spike", p["severity"], customer, members,
                    f"Week {weekly.index[pos]}: {current:,.2f} versus an average of {baseline:,.2f} over the "
                    f"previous {len(history)} weeks (x{current / max(baseline, 1.0):.1f})."))
    return alerts


def round_amounts(df: pd.DataFrame, p: dict) -> list[dict]:
    mask = (df["amount"] >= p["min_amount"]) & ((df["amount"] % p["round_base"]) == 0)
    alerts = []
    window = pd.Timedelta(days=p["window_days"])
    for customer, grp in df[mask].groupby("customer_id"):
        for chunk in _greedy_windows(grp, window, p["min_count"], 0):
            alerts.append(_alert(
                "round_amounts", p["severity"], customer, chunk,
                f"{len(chunk)} round-number transactions (multiples of {p['round_base']:,.0f}) within "
                f"{p['window_days']} days."))
    return alerts


RULES: dict[str, Callable[[pd.DataFrame, dict], list[dict]]] = {
    "cash_threshold": cash_threshold,
    "structuring": structuring,
    "rapid_movement": rapid_movement,
    "high_risk_country": high_risk_country,
    "velocity_spike": velocity_spike,
    "round_amounts": round_amounts,
}


def run_rules(df: pd.DataFrame, rules: dict | None = None) -> pd.DataFrame:
    """Run every enabled rule and return a sorted alert table."""
    rules = rules or load_rules()
    unknown = set(rules) - set(RULES)
    if unknown:
        raise ValueError(f"Unknown rule(s) in config: {sorted(unknown)}")
    rows: list[dict] = []
    for name, params in rules.items():
        if params.get("enabled", True):
            rows.extend(RULES[name](df, params))
    if not rows:
        return pd.DataFrame(columns=ALERT_COLUMNS)
    alerts = pd.DataFrame(rows)
    alerts["_sev"] = alerts["severity"].map(SEVERITY_ORDER)
    alerts = alerts.sort_values(["_sev", "total_amount"], ascending=[True, False]).drop(columns="_sev")
    alerts = alerts.reset_index(drop=True)
    alerts.insert(0, "alert_id", [f"A{n:05d}" for n in range(1, len(alerts) + 1)])
    return alerts[ALERT_COLUMNS]
