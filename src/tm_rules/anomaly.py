"""Optional unsupervised check: customer-level Isolation Forest, compared with rule alerts."""
from __future__ import annotations

import pandas as pd


def customer_features(df: pd.DataFrame, risky_countries: list[str] | None = None) -> pd.DataFrame:
    risky_countries = risky_countries or []
    work = df.assign(
        is_cash=(df["channel"] == "cash").astype(float),
        is_risky=df["counterparty_country"].isin(risky_countries).astype(float),
        is_round=((df["amount"] % 1000) == 0).astype(float),
    )
    grouped = work.groupby("customer_id")
    feats = pd.DataFrame({
        "txn_count": grouped.size(),
        "total_amount": grouped["amount"].sum(),
        "mean_amount": grouped["amount"].mean(),
        "max_amount": grouped["amount"].max(),
        "std_amount": grouped["amount"].std().fillna(0.0),
        "cash_share": grouped["is_cash"].mean(),
        "risky_country_share": grouped["is_risky"].mean(),
        "round_share": grouped["is_round"].mean(),
        "distinct_countries": grouped["counterparty_country"].nunique(),
    })
    return feats


def score_anomalies(features: pd.DataFrame, contamination: float = 0.1, seed: int = 42) -> pd.DataFrame:
    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install the optional dependency: pip install 'transaction-monitoring-rules[ml]'") from exc
    scaled = StandardScaler().fit_transform(features)
    model = IsolationForest(n_estimators=200, contamination=contamination, random_state=seed).fit(scaled)
    out = features.copy()
    out["anomaly_score"] = -model.score_samples(scaled)   # higher = more unusual
    out["is_anomaly"] = model.predict(scaled) == -1
    return out.sort_values("anomaly_score", ascending=False)


def compare_with_alerts(scored: pd.DataFrame, alerts: pd.DataFrame) -> dict:
    flagged_by_rules = set(alerts["customer_id"]) if len(alerts) else set()
    anomalies = set(scored.index[scored["is_anomaly"]])
    return {
        "rules_only": sorted(flagged_by_rules - anomalies),
        "model_only": sorted(anomalies - flagged_by_rules),
        "both": sorted(flagged_by_rules & anomalies),
    }
