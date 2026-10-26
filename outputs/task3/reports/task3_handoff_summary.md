# Task 3 technical handoff for Tasks 4–6

The one-minute 2024 feature tables and explicit QID/source manifest are in
`../data/` and `../tables/feature_manifest.json`. The interval labelled *t*
contains onboard observations in `[t-1 minute, t)`; external channels use a
prior raw timestamp no older than 60 minutes. External issue-time semantics
and engine-signal operational latency are not verified.

The frozen protocol is January–June training, August validation, September–
October coverage stress, July/November quality quarantine, and a single
December holdout. The selected restricted-onboard boosting pipeline uses six
channels and is saved in `../models/selected_pipeline.joblib`.

August selection MAE: **942.5 kW** on **35,086**
headline minutes. December holdout: **822.3 kW MAE**,
**1,064.4 kW RMSE**, **0.004 R** on
**39,270** headline minutes. December mean residual was
**-794.4 kW** (observed minus predicted). Near-zero
December correlation and persistent bias prevent a deployment-readiness claim,
despite MAE beating the training-mean and speed-cubic baselines.

For later tasks, carry forward the label-scope coverage, broader-label
sensitivity, target-calibration uncertainty, timestamp availability caveats,
daily-block errors and no-fuel-savings conclusion. Do not retune on December;
define a new later-period holdout after resolving target and timing metadata.
Task 3 QA: **18 PASS, 0 FAIL**. Full methods and evidence are in
`task3_technical_report.md` and the generated tables and figures.
