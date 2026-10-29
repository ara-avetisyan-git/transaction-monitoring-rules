"""Command-line interface for the monitoring rules."""
from __future__ import annotations

import argparse

import pandas as pd

from .data import read_transactions
from .engine import load_rules, run_rules
from .sample_data import generate


def _cmd_sample(args) -> int:
    df = generate(seed=args.seed)
    df.to_csv(args.output, index=False)
    print(f"Wrote {len(df)} synthetic transactions for {df['customer_id'].nunique()} customers to {args.output}")
    return 0


def _cmd_run(args) -> int:
    df = read_transactions(args.transactions)
    alerts = run_rules(df, load_rules(args.rules))
    alerts.to_csv(args.output, index=False)
    print(f"{len(df)} transactions, {df['customer_id'].nunique()} customers -> {len(alerts)} alerts ({args.output})")
    if len(alerts):
        print(alerts.groupby(["rule_id", "severity"]).size().rename("alerts").to_string())
    return 0


def _cmd_anomaly(args) -> int:
    from .anomaly import compare_with_alerts, customer_features as _f, score_anomalies

    df = read_transactions(args.transactions)
    rules = load_rules(args.rules)
    risky = rules.get("high_risk_country", {}).get("countries", [])
    scored = score_anomalies(_f(df, risky), contamination=args.contamination)
    alerts = run_rules(df, rules)
    overlap = compare_with_alerts(scored, alerts)
    print(f"Top {args.top} unusual customers (Isolation Forest):")
    print(scored.head(args.top)[["txn_count", "total_amount", "max_amount", "anomaly_score"]].round(2).to_string())
    print(f"\nFlagged by both rules and model: {len(overlap['both'])}")
    print(f"Rules only: {len(overlap['rules_only'])}   Model only: {len(overlap['model_only'])}")
    if overlap["model_only"]:
        print("Model-only customers (candidates for new rules): " + ", ".join(overlap["model_only"][:10]))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tm-rules", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("sample", help="Generate a synthetic transaction file")
    p.add_argument("--output", required=True)
    p.add_argument("--seed", type=int, default=42)
    p.set_defaults(func=_cmd_sample)

    p = sub.add_parser("run", help="Run the monitoring rules")
    p.add_argument("--transactions", required=True)
    p.add_argument("--rules")
    p.add_argument("--output", required=True)
    p.set_defaults(func=_cmd_run)

    p = sub.add_parser("anomaly", help="Compare rule alerts with an Isolation Forest (needs scikit-learn)")
    p.add_argument("--transactions", required=True)
    p.add_argument("--rules")
    p.add_argument("--contamination", type=float, default=0.1)
    p.add_argument("--top", type=int, default=10)
    p.set_defaults(func=_cmd_anomaly)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        print(f"Error: {exc}")
        return 2
