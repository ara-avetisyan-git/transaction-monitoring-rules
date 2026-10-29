# Notes on tuning and limits

**Rules before models.** Rules are explainable and map directly to typologies the regulator knows. The anomaly check
is deliberately a *comparison*: customers flagged only by the model are candidates for new rules, customers flagged only
by rules show where the model is blind.

**Thresholds trade detection against workload.** Lowering `structuring.min_total` or `round_amounts.min_count` finds more
patterns and creates more false positives. Calibrate on historical data and document the decision.

**Greedy, non-overlapping windows.** Structuring and round-amount rules emit one alert per pattern instead of one per
overlapping window, to keep analyst workload realistic.

**Segment baselines.** `velocity_spike` compares a customer with its *own* history. A production system also compares
with peer groups (segment, product, country).

**Not covered.** Network/linked-party analysis, real-time scoring, multi-currency conversion, alert case management.
