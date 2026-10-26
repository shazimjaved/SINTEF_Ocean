"""Generate the Task 3 technical report from executed, frozen result tables."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path("outputs/task3")
TABLES = BASE / "tables"
REPORTS = BASE / "reports"


def number(value, digits=1):
    return "undefined" if pd.isna(value) else f"{value:,.{digits}f}"


def md_table(headers, rows):
    return "| " + " | ".join(headers) + " |\n| " + " | ".join(["---"] * len(headers)) + " |\n" + "\n".join(
        "| " + " | ".join(map(str, row)) + " |" for row in rows)


def main():
    freeze = json.loads((TABLES / "frozen_selection.json").read_text(encoding="utf-8"))
    build = pd.read_csv(TABLES / "feature_build_summary.csv")
    coverage = pd.read_csv(TABLES / "label_scope_train_validation.csv")
    validation = pd.read_csv(TABLES / "validation_model_comparison.csv")
    stress = pd.read_csv(TABLES / "stress_metrics.csv")
    test = pd.read_csv(TABLES / "test_metrics.csv")
    weather = pd.read_csv(TABLES / "weather_availability_sensitivity.csv")
    daily = pd.read_csv(TABLES / "test_daily_error.csv")
    speed = pd.read_csv(TABLES / "test_speed_error.csv")
    operating = pd.read_csv(TABLES / "test_operating_condition_error.csv")
    dist = pd.read_csv(TABLES / "test_distribution_diagnostic.csv").iloc[0]
    qa = pd.read_csv(TABLES / "task3_qa.csv")
    diagnostics = json.loads((TABLES / "test_diagnostics.json").read_text(encoding="utf-8"))
    val_final = pd.read_csv(TABLES / "validation_selected_predictions.csv")
    val_final_error = val_final.actual_kw - val_final.predicted_kw
    selected = freeze["selected"]
    chosen = test[(test.scope == "headline") & (test.model == "selected_model")].iloc[0]
    test_broad = test[(test.scope == "broader_forward") & (test.model == "selected_model")].iloc[0]
    stress_head = stress[(stress.scope == "headline") & (stress.model == "selected_model")].iloc[0]
    stress_broad = stress[(stress.scope == "broader_forward") & (stress.model == "selected_model")].iloc[0]

    build_table = md_table(
        ["Month", "Raw rows", "Completed min", "Target min", "Min with negative target reading"],
        [[f"2024-{int(r.month):02d}", f"{int(r.raw_rows):,}", f"{int(r.completed_minutes):,}",
          f"{int(r.target_minutes):,}", f"{int(r.negative_target_minutes):,}"] for r in build.itertuples()])
    coverage_table = md_table(
        ["Split", "Calendar min", "Target min", "Forward min with target", "Headline min", "Headline / forward"],
        [[r.split, f"{int(r.completed_minutes):,}", f"{int(r.target_minutes):,}",
          f"{int(r.forward_with_target):,}", f"{int(r.headline_minutes):,}",
          f"{r.headline_pct_of_forward:.1f}%"] for r in coverage.itertuples()])
    val_table = md_table(
        ["Feature set", "Model", "Setting", "August n", "MAE kW", "RMSE kW", "R"],
        [[r.feature_set, r.family, r.parameter, f"{int(r.n):,}", number(r.mae_kw),
          number(r.rmse_kw), number(r.pearson_r, 3)] for r in validation.itertuples()])
    perf_table = md_table(
        ["Period", "Label scope", "Model", "n", "MAE kW", "RMSE kW", "R"],
        [["Sep-Oct" if r.split.startswith("sep") else "December", r.scope, r.model,
          f"{int(r.n):,}", number(r.mae_kw), number(r.rmse_kw), number(r.pearson_r, 3)]
         for r in list(stress.itertuples()) + list(test.itertuples())])
    speed_table = md_table(
        ["STW kn", "n", "MAE kW", "Bias kW"],
        [[r.speed_bin_kn, f"{int(r.n):,}", number(r.mae_kw), number(r.bias_kw)]
         for r in speed.itertuples()])
    operating_table = md_table(
        ["Condition", "Bin", "n", "MAE kW", "Bias kW"],
        [[r.condition, r.bin, f"{int(r.n):,}", number(r.mae_kw), number(r.bias_kw)]
         for r in operating.itertuples()])
    weather_table = md_table(
        ["Period", "Scope", "n", "All 14 fresh", "Any fresh"],
        [[r.split, r.scope, f"{int(r.n):,}", f"{r.all14_fresh_pct:.1f}%",
          f"{r.any_fresh_pct:.1f}%"] for r in weather.itertuples()])
    daily_table = md_table(
        ["Date", "n", "MAE kW", "Bias kW"],
        [[r.date, f"{int(r.n):,}", number(r.mae_kw), number(r.bias_kw)]
         for r in daily.sort_values("mae_kw", ascending=False).head(5).itertuples()])
    quantile_table = md_table(
        ["Residual quantile", "Observed minus predicted, kW"],
        [[q, number(v)] for q, v in diagnostics["residual_quantiles_kw"].items()])
    train_fit_s = validation.loc[~validation.family.isin(["training_mean", "speed_cubic"]), "fit_seconds"].sum()
    qa_pass = int((qa.status == "PASS").sum())
    qa_fail = int((qa.status == "FAIL").sum())

    report = f"""# Task 3 — Methods, Analysis and Technical Evaluation

**SINTEF Ocean Real Vessel Data Challenge · NTNU TDT4259 · technical draft, 25 October 2026**

**Status.** This is an executed CPU-only modelling and evaluation study, with a frozen August-selected configuration and one December holdout evaluation. It is suitable as a technical Task 3 draft. It does **not** establish operational deployment readiness, causally available provider weather, a validated torquemeter calibration, fuel savings, or a ship-specific physical speed–power law. The donor vessel must remain confidential.

## Executive findings

The selected approach was a histogram gradient boosting regressor using the six restricted onboard operational channels (16 transformed value, circular and count inputs). On August validation, the selection fit achieved **{number(selected['score'])} kW MAE**. A subsequent fit of the same frozen configuration on all **{freeze['final_fit_n']:,}** eligible January–June minutes achieved **{number(np.abs(val_final_error).mean())} kW MAE**, **{number(np.sqrt(np.square(val_final_error).mean()))} kW RMSE** and **{number(val_final.actual_kw.corr(val_final.predicted_kw), 3)} R** on August. The latter is descriptive after selection, not a second tuning criterion.

The one-time December holdout scored **{number(chosen.mae_kw)} kW MAE**, **{number(chosen.rmse_kw)} kW RMSE**, and **{number(chosen.pearson_r, 3)} R** on **{int(chosen.n):,}** headline minutes. It beat the training-mean and constrained speed-cubic baselines on MAE, yet December R was almost zero. Mean residual (observed minus predicted) was **{number(dist.mean_residual_kw)} kW**: predictions were systematically high. Therefore the December result does not support a claim that this model tracks minute-scale power variation reliably. There was no post-test retuning.

The main scientific fragility is label scope. September–October headline MAE was **{number(stress_head.mae_kw)} kW**, while the broader forward-speed subset, which retains zero and negative labels, had **{number(stress_broad.mae_kw)} kW MAE**. These are different estimands and must not be pooled or portrayed as equivalent performance. Negative power can reflect reverse operation, a sensor problem, or another mechanism; the data alone do not decide which.

## 1. Data, provenance and boundaries

The year-wide input is twelve confidential 2024 long-format CSVs with **{int(build.raw_rows.sum()):,}** records. January 2025 has no power target and is not used for supervised training or evaluation. Noon Reports are excluded from model features because their publication time relative to a prediction is unknown. The existing Task 1 and Task 2 preliminary reports, dictionary and QID map remain the reference for sensor provenance and quality context.

The streaming builder reads one monthly file at a time in 200,000-row chunks. It does not materialize the 42-million-row source or a union-timestamp pivot. Its 2024 output has **{int(build.completed_minutes.sum()):,}** completed-minute rows, compressed into twelve files totalling **{build.output_bytes.sum()/1e6:.1f} MB**. Every exported predictor is explicitly keyed by QID in `feature_manifest.json`. The four constant-zero draft channels, six torquemeter-associated inputs and the sparse depth channel are absent from the exported modelling table. The power target and separate label-quality fields remain for evaluation only; the fitted pipeline accepts only its explicit feature-column list.

For the row labelled time *t*, onboard channels use raw observations in **[t − 1 minute, t)** and are summarized at the interval end. Numeric scalar channels use arithmetic means. Heading and relative wind angle use vector sums of sine and cosine, then a circular mean; the model receives sine, cosine and resultant length, not an ordinary arithmetic mean of degrees. Onboard `n__` fields record raw observations per window. External provider channels use the latest raw timestamp strictly before the completed-minute end, with a maximum source age of 3,600 seconds; `age_s__` fields retain that provenance. No reading after *t* is used. This is a completed-minute reconstruction, not proof that every input existed at a real operational decision instant. Provider timestamps might denote valid time rather than issue time.

The input sensor values are numeric after parsing; the raw CSV stores text. Timezone semantics for 2024 `Z` timestamps are UTC. January 2025 timestamp timezone remains unverified, but January 2025 is outside this supervised study. The year-wide exact duplicate audit in Task 2 found no duplicate `(timestamp, QID)` keys. The Task 3 builder independently reconciles per-month source row and target-reading counts.

### Monthly build and target counts

{build_table}

The target-minute column counts completed minutes with at least one power observation; it is not an uptime percentage. September and October have lower target observation-count density, and this is evaluated separately. July and November remain available as source data and are quarantined from fitting and ranking because of target anomalies; their negative-reading counts alone do not diagnose the fault mechanism.

## 2. Split, label scope and leakage controls

The split was fixed before fitting: January–June training; July quality quarantine; August validation and model selection; September–October coverage stress; November quality quarantine; December untouched final holdout. There is no random split, and no December metric enters feature, hyperparameter or label-rule selection. The December evaluation script requires a saved frozen selection and refuses a second execution while its prediction artifact exists.

The predeclared headline estimand is forward underway completed minutes with speed through water at least 3 kn, an observed target, positive minute-mean target, nonnegative minimum raw target in that minute, and zero negative raw target readings in that minute. The 3 kn boundary defines operational scope; it is not claimed as a calibrated anomaly threshold. The broader sensitivity set keeps all target values at the same forward-speed boundary, including zero and negative values. These labels can be physically legitimate in different operations; retaining them in the broader analysis prevents silent deletion.

{coverage_table}

These counts show that headline coverage differs by period. On August, **{int(coverage.loc[coverage.split=='validation','headline_minutes'].iloc[0]):,}** of **{int(coverage.loc[coverage.split=='validation','forward_with_target'].iloc[0]):,}** forward minutes with target meet the headline rule. Zero or negative target minutes at forward speed warrant vessel and sensor review. The headline metric must always be accompanied by its sample count and the broader-label sensitivity result.

Feature provenance is bounded by the completed-minute end. Target, target counts, target minimum, torquemeter RPM/torque/energy/thrust, draft and depth do not enter the model input array. Imputation indicators and medians are learned within each training pipeline on January–June only. Ridge scaling is fitted in that same pipeline. No global interpolation or imputation crosses the chronological partitions. A persistence baseline is omitted from the ranking because a prior trustworthy power reading at the decision instant is not verified; presenting it as deployable would assume the missing operational contract.

## 3. Model families and selection procedure

Three feature sets were compared. **A: restricted onboard** uses speed through water, speed over ground, true heading, turn rate, relative wind speed and relative wind angle. **B: extended onboard** adds four main-engine channels: scavenging-air pressure, turbocharger RPM transducer, fuel load and CAMS RPM. **C: exploratory weather** adds all fourteen provider channels to B. C is a retrospective sensitivity case because provider issue-time semantics are unresolved. All angular channels are encoded with sine and cosine; onboard angle concentration is retained as a quality descriptor.

The two baselines are the constant training mean and an empirical nonnegative speed-cubic function `P = a + b·STW³` with both coefficients fitted on training data by nonnegative least squares. The latter is a simple physically motivated comparator, not a first-principles propulsion law or an assertion of a monotone observed relationship in every regime. Ridge Regression uses training-only median imputation, missingness flags and scaling, with alpha 10 or 100. HistGradientBoostingRegressor uses training-only median imputation and missingness flags, 120 boosting iterations, learning rate 0.07, minimum leaf size 80, L2 regularization 1 and 15 or 31 leaves. Searches are intentionally small for an 8 GB CPU laptop.

For fair bounded comparison, each candidate was fitted to the same deterministic, uniformly spaced **{freeze['max_selection_fit_rows']:,}** eligible January–June rows, then scored on all eligible August rows. The primary selection statistic was August MAE; RMSE and Pearson R were reported but did not override MAE. The selected model was then refitted on all **{freeze['final_fit_n']:,}** eligible January–June rows. The baseline coefficients used in final stress and holdout evaluation were likewise fitted on all eligible training rows. No August, September, October, November or December labels entered the final model fit.

### August model comparison

{val_table}

The restricted onboard boosting model had the lowest August MAE. Some extended configurations have high R but worse absolute error, which illustrates why correlation alone is not a sufficient power-estimation criterion. The August comparison is a chronological validation result, not evidence of generalization to all operating periods.

## 4. Coverage stress and untouched holdout

{perf_table}

Pearson R for the constant training-mean baseline is undefined and intentionally blank. The December headline covers **{int(chosen.n):,}** of **{int(chosen.forward_with_target):,}** forward minutes with target, and **{int(chosen.target_minutes):,}** of **{int(chosen.completed_minutes):,}** calendar minutes have any target reading. The broader December sensitivity differs little from the headline because only **{int(chosen.forward_with_target-chosen.headline_minutes):,}** forward minutes with target fall outside the positive-label rule. September–October is very different: the broader set contains **{int(stress_broad.n-stress_head.n):,}** additional forward minutes with zero or negative label conditions, and the selected model's MAE rises sharply. This must be investigated before claiming coverage across operating states.

The December observed target has mean **{number(dist.actual_mean_kw)} kW** and standard deviation **{number(dist.actual_std_kw)} kW** on headline minutes; predictions have mean **{number(dist.predicted_mean_kw)} kW** and standard deviation **{number(dist.predicted_std_kw)} kW**. The much lower observed variation and negative mean residual are consistent with a period shift, calibration difference, operating-state difference, or missing explanatory variables. These are hypotheses, not diagnosed causes. No December-based correction has been applied.

![December prediction versus actual](../figures/test_prediction_vs_actual.png)

![December residual distribution](../figures/test_residual_distribution.png)

### Error distribution and temporal blocks

Residual means observed minus predicted. The saved prediction table contains the exact one-time December predictions, labels, speed, target-quality indicators and weather-presence flags. Its residual quantiles are:

{quantile_table}

There are **{diagnostics['daily_blocks']}** calendar days with at least one headline minute in December. The largest five daily MAEs are shown below; days with few observations should not be interpreted as equally precise estimates. Daily blocks expose persistence of errors that per-minute counts conceal.

{daily_table}

![Daily December MAE](../figures/test_daily_mae.png)

### Speed and operating conditions

{speed_table}

![December error by speed](../figures/test_error_vs_speed.png)

The following descriptive bins add relative wind speed, absolute turn rate and speed over ground. Bins were computed after the holdout evaluation for diagnosis only; they were not used to change the fitted model or headline scope. Sparse bins carry large uncertainty.

{operating_table}

![December error by operating conditions](../figures/test_operating_condition_error.png)

### Weather availability sensitivity

{weather_table}

All fourteen provider columns are fresh under the retrospective **raw-timestamp age ≤ 60 minutes** rule in the evaluated forward subsets. This is a data-coverage fact, not evidence that the values had actually been issued by those times. The winning model uses no external weather features, so weather availability does not alter its December predictions. Feature set C performed worse than A on August MAE; provider causality and real-time availability still require metadata before any operational use.

## 5. Technical validity, resource use and reproducibility

The feature pass took **{number(build.elapsed_s.sum())} seconds** summed over months on this machine; the twelve bounded candidate model fits took **{number(train_fit_s)} seconds** summed over fit calls, and the final selected fit took **{number(freeze['final_fit_seconds'])} seconds**. Stress plus one-time holdout evaluation and figure generation took **{number(diagnostics['eval_seconds'])} seconds**. These timings are local observations and exclude environment setup and report writing. Peak RAM was not measured. The implementation limits raw ingestion to 200,000 rows per chunk, materializes at most one monthly minute grid in the builder, and limits selection fits to 120,000 rows; it uses CPU-only scikit-learn and compact compressed CSV outputs. The final fitted pipeline is serialized with joblib.

Task 3's executable QA currently records **{qa_pass} PASS** and **{qa_fail} FAIL**. It includes synthetic boundary cases for no future within-window onboard values, no future provider value, circular 350°/10° aggregation; source row and target-count reconciliation; QID and feature exclusions; provider age bounds; frozen split and model-input checks; independent recomputation of December MAE/RMSE/R from saved predictions; and undefined-R handling for constant baselines. The Task 1/2 checklist remains a separate preliminary audit and is not replaced by this Task 3 checklist.

Reproduction from the project root follows `outputs/task3/README.md`: scripts 11, 12, 13, 14, 15 and 16 in order. Script 13 will refuse to overwrite the holdout predictions. A fresh rerun intended as a new experiment should preserve this completed holdout and use a clearly versioned experiment directory; it must not silently retune on December.

## 6. Remaining scientific limitations and next work

1. **Power-label validity.** The mechanism and exact boundaries of July and November anomalies remain unknown. August's forward-speed zero/negative labels and September–October's much larger broader-label error also require investigation. Calibration and operations logs are needed before expanding the headline scope or asserting which negative values are faults.
2. **Temporal availability.** Onboard features describe a completed minute. Engine-signal and target operational latency were not established. Provider timestamp issue, validity and timezone semantics remain unknown; external-feature results are exploratory and must not be marketed as causal real-time forecasts.
3. **December transfer.** December R near zero and a sizeable negative bias demonstrate weak transfer of minute-scale variation, despite MAE beating the two simple baselines. Test findings may motivate a *new* future protocol and new holdout, but December cannot be reused for tuning this reported experiment.
4. **Dependence and uncertainty.** Adjacent minute errors are autocorrelated, weather timestamps repeat across minutes, and vessel operating periods are clustered. Per-minute sample counts are not independent trials. Day or voyage-block uncertainty estimates should accompany later comparative claims.
5. **Scope and outcomes.** No fuel-consumption target, cost, emissions or intervention was validated here. No fuel saving, route optimization benefit, or causal effect is estimated. These findings should inform Tasks 4–6 only as a reproducible technical starting point.

For Tasks 4–6, reuse the explicit QID manifest, minute-window contract, frozen split, label-scope flags, saved model-comparison tables, residual diagnostics and the conservative availability caveats. The next scientific gate is to reconcile target calibration and operational timestamps with vessel/provider metadata, then define a new prospective or later-period holdout before changing the model. The present December holdout is spent for this experiment.

## Artifact index

- `data/minute_2024_MM.csv.gz`: twelve reusable one-minute tables; `tables/feature_manifest.json`: QID/source and interval contract.
- `tables/feature_build_summary.csv`, `label_scope_train_validation.csv`, `validation_model_comparison.csv`, `frozen_selection.json`: build, coverage, selection and frozen protocol.
- `models/selected_pipeline.joblib`: selected, training-only fitted pipeline and metadata.
- `tables/stress_metrics.csv`, `test_metrics.csv`, `test_predictions.csv.gz`, `test_daily_error.csv`, `test_speed_error.csv`, `test_operating_condition_error.csv`, `test_distribution_diagnostic.csv`, `weather_availability_sensitivity.csv`: genuine validation and holdout evidence.
- `figures/`: plots drawn from saved December results; `tables/task3_qa.csv`: executable check results; `README.md`: commands and safeguards.

**Interpretation rule:** all metrics are period-, label-scope- and availability-dependent. Do not reuse a headline number without its split, sample count and unresolved limitations.
"""
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / "task3_technical_report.md"
    path.write_text(report, encoding="utf-8")
    handoff = f"""# Task 3 technical handoff for Tasks 4–6

The one-minute 2024 feature tables and explicit QID/source manifest are in
`../data/` and `../tables/feature_manifest.json`. The interval labelled *t*
contains onboard observations in `[t-1 minute, t)`; external channels use a
prior raw timestamp no older than 60 minutes. External issue-time semantics
and engine-signal operational latency are not verified.

The frozen protocol is January–June training, August validation, September–
October coverage stress, July/November quality quarantine, and a single
December holdout. The selected restricted-onboard boosting pipeline uses six
channels and is saved in `../models/selected_pipeline.joblib`.

August selection MAE: **{number(selected['score'])} kW** on **{len(val_final):,}**
headline minutes. December holdout: **{number(chosen.mae_kw)} kW MAE**,
**{number(chosen.rmse_kw)} kW RMSE**, **{number(chosen.pearson_r, 3)} R** on
**{int(chosen.n):,}** headline minutes. December mean residual was
**{number(dist.mean_residual_kw)} kW** (observed minus predicted). Near-zero
December correlation and persistent bias prevent a deployment-readiness claim,
despite MAE beating the training-mean and speed-cubic baselines.

For later tasks, carry forward the label-scope coverage, broader-label
sensitivity, target-calibration uncertainty, timestamp availability caveats,
daily-block errors and no-fuel-savings conclusion. Do not retune on December;
define a new later-period holdout after resolving target and timing metadata.
Task 3 QA: **{qa_pass} PASS, {qa_fail} FAIL**. Full methods and evidence are in
`task3_technical_report.md` and the generated tables and figures.
"""
    (REPORTS / "task3_handoff_summary.md").write_text(handoff, encoding="utf-8")
    print(f"Wrote {path} ({len(report.split()):,} words); QA {qa_pass} PASS, {qa_fail} FAIL")


if __name__ == "__main__":
    main()
