# Task 3 execution record — 25 October 2026

- Added bounded-memory monthly feature builder, explicit QID manifest, circular
  aggregation, completed-minute labels, provider source ages and target-quality
  indicators. The first one-month trial failed because pandas returned
  microsecond timestamps; the builder now converts explicitly to nanoseconds.
  A full 12-month run then exited 0. A subsequent full run removed excluded
  proxy channels from the exported feature tables and exited 0.
- Added training-only preprocessing, fixed chronological selection, two simple
  baselines, Ridge and bounded histogram boosting. An initial training run
  failed at a pandas mean call before freezing any model or reading December;
  the corrected full run exited 0 and froze the selected configuration.
- Added stress and holdout evaluation. The first evaluation attempt failed on
  an angular-provider diagnostic column while processing September–October,
  before opening December. The corrected run exited 0 and evaluated December
  once. `test_predictions.csv.gz` now guards against another test run.
- Added daily, speed and operating-condition diagnostics. A constant training
  mean has undefined Pearson R; the metric function and already saved CSV cells
  were corrected without fitting or predicting again.
- Executed Task 3 QA: **18 PASS, 0 FAIL**. The technical report is generated
  from saved tables. Task 1/2 reports, raw sensor CSVs, Noon Reports, prior
  figures and the preliminary split file were not changed.

The completed Task 3 holdout has near-zero Pearson R and sizeable systematic
overprediction. These findings are reported as limitations; no test-driven
model change was made.

## Post-freeze scientific audit

- Preserved the original model, frozen selection, December predictions, original
  result tables and first Task 3 report. SHA256 hashes were checked before and
  after the audit.
- Added separate Pearson-r and sklearn-R² columns in a new metric audit table.
  Direct R² was computed from saved final-fit August and original December
  predictions, and from saved stress predictions reproduced with the frozen
  model. The 14 August selection-era candidate rows have algebraic R² from
  full-precision RMSE and common August labels because their prediction vectors
  were not saved; this remains explicitly unresolved for direct recomputation.
- Added distribution and target-conditional coverage audits. December headline
  R² is approximately −7.953, with near-zero Pearson r and mean residual about
  −794 kW. These are reported without diagnosing the cause.
- Added count-labelled diagnostic plots while retaining the original figures.
  A missing relative-wind bin accounts for 94 observations, and the highest
  turn-rate bin contains only eight observations.
- Produced a 46-page academic Markdown/PDF report and a separate detailed
  technical appendix. The new scientific QA run recorded **16 PASS, 0 FAIL,
  1 UNRESOLVED**. No model was fitted or selected in this audit.
