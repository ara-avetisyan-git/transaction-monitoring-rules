import pandas as pd
import pytest

from tm_rules.cli import main
from tm_rules.data import prepare
from tm_rules.engine import load_rules, run_rules
from tm_rules.sample_data import PLANTED, generate


@pytest.fixture(scope="module")
def df():
    return prepare(generate(seed=42))


@pytest.fixture(scope="module")
def alerts(df):
    return run_rules(df, load_rules())


def test_every_planted_pattern_is_detected(alerts):
    found = {(r.customer_id, r.rule_id) for r in alerts.itertuples()}
    for customer, rule in PLANTED.items():
        assert (customer, rule) in found, f"{rule} did not fire for {customer}"


def test_ordinary_customers_do_not_alert(alerts):
    noisy = alerts[alerts["customer_id"].str.startswith("N")]
    assert noisy.empty, noisy[["customer_id", "rule_id", "description"]].to_string()


def test_alerts_are_explained_and_traceable(alerts, df):
    assert alerts["description"].str.len().gt(20).all()
    known = set(df["txn_id"])
    for ids in alerts["txn_ids"]:
        assert set(ids.split(";")) <= known


def test_structuring_alert_covers_all_four_deposits(alerts):
    row = alerts[(alerts.customer_id == "P_STRUCT") & (alerts.rule_id == "structuring")].iloc[0]
    assert row.txn_count == 4 and row.total_amount == 37900.0 and row.severity == "high"


def test_passthrough_alert_values(alerts):
    row = alerts[alerts.rule_id == "rapid_movement"].iloc[0]
    assert row.total_amount == 20000.0 + 19500.0


def test_disabling_a_rule_removes_its_alerts(df):
    rules = load_rules()
    rules["structuring"]["enabled"] = False
    assert "structuring" not in set(run_rules(df, rules)["rule_id"])


def test_threshold_change_changes_outcome(df):
    rules = load_rules()
    rules["cash_threshold"]["threshold"] = 9000
    cash_alerts = run_rules(df, rules).query("rule_id == 'cash_threshold'")
    assert {"P_CASH", "P_STRUCT"} <= set(cash_alerts["customer_id"])


def test_results_are_deterministic(df):
    assert run_rules(df, load_rules()).equals(run_rules(df, load_rules()))


def test_unknown_rule_is_rejected(df):
    with pytest.raises(ValueError, match="Unknown rule"):
        run_rules(df, {"made_up_rule": {"enabled": True}})


def test_input_validation():
    with pytest.raises(ValueError, match="missing columns"):
        prepare(pd.DataFrame({"txn_id": ["1"]}))
    bad = generate().head(3).assign(direction="sideways")
    with pytest.raises(ValueError, match="direction"):
        prepare(bad)


def test_cli_end_to_end(tmp_path, capsys):
    tx, out = tmp_path / "tx.csv", tmp_path / "alerts.csv"
    assert main(["sample", "--output", str(tx)]) == 0
    assert main(["run", "--transactions", str(tx), "--output", str(out)]) == 0
    assert out.exists() and "alerts" in capsys.readouterr().out
