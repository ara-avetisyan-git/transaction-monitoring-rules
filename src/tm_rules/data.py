"""Loading and validating the transaction file."""
from __future__ import annotations

import pandas as pd

REQUIRED = ["txn_id", "timestamp", "customer_id", "direction", "amount", "channel", "counterparty_country"]


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Validate columns and normalize types; returns a copy sorted by time."""
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Transaction file is missing columns: {', '.join(missing)}")
    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="raise")
    out["amount"] = pd.to_numeric(out["amount"], errors="raise").abs()
    out["direction"] = out["direction"].astype(str).str.strip().str.lower()
    bad = set(out["direction"]) - {"in", "out"}
    if bad:
        raise ValueError(f"direction must be 'in' or 'out', found: {sorted(bad)}")
    out["channel"] = out["channel"].astype(str).str.strip().str.lower()
    out["counterparty_country"] = out["counterparty_country"].fillna("").astype(str).str.strip().str.upper()
    out["customer_id"] = out["customer_id"].astype(str)
    if out["txn_id"].duplicated().any():
        raise ValueError("txn_id values must be unique")
    return out.sort_values(["timestamp", "txn_id"]).reset_index(drop=True)


def read_transactions(path: str) -> pd.DataFrame:
    return prepare(pd.read_csv(path, dtype={"txn_id": str, "customer_id": str}))
