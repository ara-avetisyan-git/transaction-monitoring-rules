# transaction-monitoring-rules

[![CI](https://github.com/ara-avetisyan-git/transaction-monitoring-rules/actions/workflows/ci.yml/badge.svg)](https://github.com/ara-avetisyan-git/transaction-monitoring-rules/actions)

A small, readable **transaction monitoring rule engine** with explainable alerts, plus an optional unsupervised
(Isolation Forest) check that shows what the rules miss. Runs on synthetic data with planted suspicious patterns,
so every rule can be tested.

| Rule | Typology |
|---|---|
| `cash_threshold` | Single large cash transaction |
| `structuring` | Several just-below-threshold cash transactions within days |
| `rapid_movement` | Funds in, nearly the same amount out within hours (pass-through / layering) |
| `high_risk_country` | Counterparties in high-risk jurisdictions |
| `velocity_spike` | A week far above the customer's own recent baseline |
| `round_amounts` | Repeated round-number transfers |

Each alert has a rule, severity, customer, the exact transaction IDs, the amount and window, and a **human-readable reason**.
Thresholds live in [rules.yaml](src/tm_rules/rules.yaml).

## Install and run

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q

tm-rules sample  --output tx.csv                       # synthetic customers + planted patterns
tm-rules run     --transactions tx.csv --output alerts.csv
tm-rules anomaly --transactions tx.csv                 # rules vs. Isolation Forest (needs scikit-learn)
```

Input columns: `txn_id, timestamp, customer_id, direction (in/out), amount, channel, counterparty_country`.

## What the tests prove

- every planted pattern is detected by the intended rule;
- the 40 ordinary customers produce **no** alerts with the default thresholds;
- every alert points to real transactions; results are deterministic; thresholds can be changed and disabled per rule.

See [docs/NOTES.md](docs/NOTES.md) for tuning and the limits of this approach.

## Limitations

Illustrative thresholds, one currency, batch (not real-time) processing, no customer-segment baselines.
Real programmes need calibration, below-the-line testing and a documented alert-handling workflow.

## License

MIT. Author: Ara Avetisyan, AML/CFT compliance - [LinkedIn](https://www.linkedin.com/in/ara-avetisyan-1795802a)
