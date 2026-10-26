# Task 3 reproducibility

Run from the project root in a local Python 3.11+ environment with
`pip install -r requirements.txt`. Raw vessel and Noon Report files stay local.
All Task 3 outputs are under `outputs/task3/`.

```powershell
python -B scripts/11_task3_features.py
python -B scripts/12_task3_train_validate.py
python -B scripts/13_task3_evaluate.py
python -B scripts/14_task3_qa.py
python -B scripts/15_task3_diagnostics.py
python -B scripts/16_task3_report.py
```

Script 11 streams each 2024 CSV in 200,000-row chunks and writes one compressed
minute table per month. The completed-minute interval is `[end-1 min, end)`;
onboard means, circular means and target quality indicators use only rows in
that interval. Provider values use the latest raw timestamp before the end,
up to 3600 seconds old. `age_s__*` columns preserve source-age provenance.
Provider timestamp issue/validity semantics are unknown, so provider features
remain exploratory. The exported tables contain only the 24 candidate channels,
the target and label-quality fields. The manifest preserves QIDs and sources.

Script 12 reads January-June and August only. It fits imputation and scaling
inside each training pipeline, compares bounded Ridge and histogram boosting
models against training-mean and nonnegative speed-cubic baselines, and freezes
the choice in `tables/frozen_selection.json`. It then fits the selected pipeline
on all eligible January-June minutes and saves it in `models/`.

Script 13 requires that frozen file before it opens December. It evaluates
September-October coverage stress, then December once. It refuses to run again
when `tables/test_predictions.csv.gz` exists. To keep the holdout untouched,
do not delete that guard output for exploratory retuning. Script 14 checks
synthetic temporal edge cases and the generated data/model/results. Script 15
adds descriptive operating-condition diagnostics without refitting or predicting
and corrects undefined Pearson R for constant baselines. Script 16 regenerates
the technical report from the actual tables.

The headline scope is completed minutes with a recorded power target, speed
through water at least 3 kn, positive minute-mean target and no negative raw
target reading within that minute. This describes forward underway operation;
it does not diagnose negative readings as sensor failures. A broader forward
subset retaining zero and negative labels is reported as sensitivity. July and
November remain quarantined, not silently discarded from source data. No same-
day Noon Report values or target-derived torquemeter channels enter models.

The optional persistence predictor is omitted from ranking because availability
of a trustworthy prior power reading at the operational decision instant is
unverified. The feature timestamp denotes the end of a completed minute; the
analysis does not establish instant or future prediction capability.

## Post-freeze scientific audit and academic report

The original December predictions, frozen selection, saved model and original
metric tables are preserved. To regenerate the separate audit outputs and the
46-page academic Markdown/PDF report without fitting or retuning, run:

```powershell
python -B scripts/17_task3_metric_science_audit.py
python -B scripts/18_task3_diagnostic_figures.py
python -B scripts/19_task3_academic_report.py
python -B scripts/20_task3_scientific_qa.py
```

The original candidate-model prediction vectors from August were not saved.
Their R² values are recovered from full-precision RMSE and identical August
labels using the SSE/SST identity and are marked algebraic. Direct sklearn R²
is recomputed from saved final-fit August and original December predictions;
stress predictions are reproduced by inference with the frozen model, saved,
and reconciled with original metrics. This audit never calls `fit`.

The academic report is `reports/task3_academic_report.pdf` (46 verified pages)
and `reports/task3_academic_report.md`. Long tables, metric provenance and
internal paths are in `reports/task3_technical_appendix.md`. New diagnostic
figures have `_audited` suffixes; original plots and result tables remain intact.
The new QA checklist is `tables/task3_scientific_qa.csv`.
The concise updated interpretation for subsequent tasks is
`reports/task3_scientific_handoff_summary.md`.
The earlier `reports/task3_technical_report.md` remains as a historical
pre-audit snapshot; use the academic report for the corrected R² and Pearson-r
interpretation.
