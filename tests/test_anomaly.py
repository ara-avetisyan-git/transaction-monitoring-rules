import pytest

pytest.importorskip("sklearn")

from tm_rules.anomaly import compare_with_alerts, customer_features, score_anomalies
from tm_rules.data import prepare
from tm_rules.engine import load_rules, run_rules
from tm_rules.sample_data import generate


def test_planted_customers_rank_as_unusual():
    df = prepare(generate(seed=42))
    scored = score_anomalies(customer_features(df, ["KP", "IR", "MM"]), contamination=0.15)
    top = set(scored.head(10).index)
    assert {"P_PASS", "P_CASH", "P_STRUCT"} <= top


def test_comparison_partitions_customers():
    df = prepare(generate(seed=42))
    scored = score_anomalies(customer_features(df), contamination=0.15)
    overlap = compare_with_alerts(scored, run_rules(df, load_rules()))
    assert overlap["both"]
    assert not set(overlap["both"]) & set(overlap["rules_only"])
