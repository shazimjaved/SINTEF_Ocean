"""Independent V6 assertions over saved predictions and compact source labels."""
from __future__ import annotations

import csv
import hashlib
import json
import runpy
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


ROOT = Path(__file__).resolve().parents[2]
assert Path.cwd().resolve() == ROOT
OUT = ROOT / "outputs" / "task3_v6"
V2_PATH = ROOT / "scripts" / "task3_v2" / "07_walkforward_experiments.py"
V2 = runpy.run_path(str(V2_PATH))
SOURCE = ROOT / "outputs" / "task3" / "data"
ARMS = {"jan_jun": [1, 2, 3, 4, 5, 6], "jan_jun_aug": [1, 2, 3, 4, 5, 6, 8]}
MONTHS = {"september": 9, "october": 10}
CANDIDATES = ["training_mean", "speed_cubic", "A_hgb_full_v1like",
              "B_hgb_full", "B_ridge_full", "B_hgb_broad_full"]
checks: list[dict] = []


def check(name: str, result: bool, evidence: str) -> None:
    checks.append({"check_id": name, "status": "PASS" if result else "FAIL", "evidence": evidence})


def source_scope(month: int) -> pd.DataFrame:
    cols = ["window_end_utc", "SHAFT_MechPower_kW", "STW_kn", "target_n",
            "target_min", "target_negative_n"]
    d = pd.read_csv(SOURCE / f"minute_2024_{month:02d}.csv.gz", usecols=cols,
                    dtype={"SHAFT_MechPower_kW": "float32", "STW_kn": "float32",
                           "target_min": "float32", "target_n": "int16",
                           "target_negative_n": "int16"})
    base = d.target_n.gt(0) & d.STW_kn.ge(3) & d.SHAFT_MechPower_kW.notna()
    d = d.loc[base].reset_index(drop=True)
    d["positive"] = (d.SHAFT_MechPower_kW.gt(0) & d.target_min.ge(0)
                     & d.target_negative_n.eq(0))
    d["recorded_zero"] = d.SHAFT_MechPower_kW.eq(0) & d.target_negative_n.eq(0)
    d["negative_or_mixed"] = ~(d.positive | d.recorded_zero)
    return d


def metric_check(y: np.ndarray, p: np.ndarray, row: pd.Series) -> bool:
    y = np.asarray(y, dtype=np.float64)
    p = np.asarray(p, dtype=np.float64)
    mae = mean_absolute_error(y, p)
    rmse = np.sqrt(mean_squared_error(y, p))
    bias = np.mean(y - p)
    constant_y = np.ptp(y) <= 1e-12
    constant_p = np.ptp(p) <= 1e-10 * max(1., abs(float(np.mean(p))))
    pearson = np.nan if constant_y or constant_p else np.corrcoef(y, p)[0, 1]
    r2 = np.nan if constant_y or len(y) < 2 else r2_score(y, p)
    return (len(y) == row.n and np.isclose(mae, row.mae_kw, atol=1e-5)
            and np.isclose(rmse, row.rmse_kw, atol=1e-5)
            and np.isclose(bias, row.bias_actual_minus_pred_kw, atol=1e-5)
            and np.isclose(np.mean(y), row.observed_mean_kw, atol=1e-5)
            and np.isclose(np.mean(p), row.predicted_mean_kw, atol=1e-5)
            and ((np.isnan(pearson) and pd.isna(row.pearson_r))
                 or np.isclose(pearson, row.pearson_r, atol=1e-10))
            and ((np.isnan(r2) and pd.isna(row.r2_score))
                 or np.isclose(r2, row.r2_score, atol=1e-10)))


def main() -> None:
    manifest = json.loads((OUT / "experiment_manifest.json").read_text(encoding="utf-8"))
    check("V6_CONFIG_01", manifest["arms"] == ARMS and manifest["evaluation_months"] == MONTHS
          and manifest["forbidden_months"] == [7, 11, 12]
          and manifest["selection"].startswith("none"),
          "Predeclared Jan-Jun versus Jan-Jun+Aug histories; Sept/Oct development only")
    check("V6_CONFIG_02", manifest["candidate_source_sha256"] ==
          hashlib.sha256(V2_PATH.read_bytes()).hexdigest()
          and [c["name"] for c in manifest["fixed_candidates"]] == CANDIDATES[2:],
          "V2 candidate definitions source-hashed and unchanged")
    from sys import path as sys_path
    sys_path.insert(0, str(ROOT / "scripts"))
    from channel_config import COLUMN_TO_SOURCE
    channel_sets = V2["A"], V2["B"]
    check("V6_FEATURE_01", all(COLUMN_TO_SOURCE[c] == "onboard" for group in channel_sets for c in group)
          and all("SHAFT_" not in col and not col.startswith("target")
                  for columns in V2["COLS"].values() for col in columns)
          and len(V2["COLS"]["A"]) == 16 and len(V2["COLS"]["B"]) == 24,
          "16 restricted and 24 extended columns; onboard source, no target/torquemeter predictors")
    fit = pd.read_csv(OUT / "fit_inventory.csv")
    check("V6_FIT_01", len(fit) == 8 and set(fit.training_arm) == set(ARMS)
          and fit.groupby("training_arm").size().eq(4).all()
          and fit.last_training_timestamp.lt("2024-09-01T00:01:00Z").all()
          and fit.loc[fit.training_arm.eq("jan_jun"), "last_training_timestamp"].lt("2024-07-01T00:01:00Z").all(),
          "Eight fits; all last training timestamps precede September labels")
    check("V6_FIT_02", set(fit.loc[fit.training_arm.eq("jan_jun"), "train_n"]) == {166154, 184295}
          and set(fit.loc[fit.training_arm.eq("jan_jun_aug"), "train_n"]) == {201240, 225500},
          "Positive/broad training counts match fixed histories")
    coverage = pd.read_csv(OUT / "evaluation_coverage.csv").set_index("evaluation_month")
    sources = {name: source_scope(month) for name, month in MONTHS.items()}
    check("V6_SCOPE_01", all(len(sources[name]) == coverage.loc[name, "forward_with_target"]
          and sources[name].positive.sum() == coverage.loc[name, "positive_n"]
          and sources[name].recorded_zero.sum() == coverage.loc[name, "recorded_zero_n"]
          and sources[name].negative_or_mixed.sum() == coverage.loc[name, "negative_or_mixed_n"]
          for name in MONTHS), "Independent source-minute scope and zero counts")
    results = pd.read_csv(OUT / "development_metrics.csv")
    check("V6_RESULT_01", len(results) == 72 and results[["training_arm", "candidate",
          "evaluation_month", "scope"]].drop_duplicates().shape[0] == 72,
          "2 arms × 6 fixed methods × 2 months × 3 scopes = 72 unique rows")
    alignment_ok = True
    metric_ok = True
    daily_ok = True
    daily = pd.read_csv(OUT / "daily_metrics.csv")
    prediction_files = list((OUT / "predictions").glob("*.csv.gz"))
    check("V6_PRED_01", len(prediction_files) == 24,
          "24 preserved prediction files: two arms, six methods, two months")
    for arm in ARMS:
        for candidate in CANDIDATES:
            for name in MONTHS:
                pred = pd.read_csv(OUT / "predictions" / f"{arm}__{candidate}__{name}.csv.gz")
                src = sources[name]
                alignment_ok &= (pred.window_end_utc.equals(src.window_end_utc)
                                 and np.allclose(pred.actual_kw, src.SHAFT_MechPower_kW,
                                                 rtol=0, atol=1e-3)
                                 and pred.positive.equals(src.positive)
                                 and pred.recorded_zero.equals(src.recorded_zero)
                                 and pred.negative_or_mixed.equals(src.negative_or_mixed))
                for scope, part in [("positive", pred[pred.positive]),
                                    ("broader_forward", pred),
                                    ("recorded_zero", pred[pred.recorded_zero])]:
                    row = results[(results.training_arm == arm) & (results.candidate == candidate)
                                  & (results.evaluation_month == name) & (results.scope == scope)]
                    metric_ok &= len(row) == 1 and metric_check(part.actual_kw, part.predicted_kw,
                                                                row.iloc[0])
                # Daily summary uses the covered minute's UTC day, not the next
                # day at a 00:00 window boundary.
                pred["date"] = (pd.to_datetime(pred.window_end_utc, utc=True)
                                - pd.Timedelta(minutes=1)).dt.strftime("%Y-%m-%d")
                for scope, part in [("positive", pred[pred.positive]),
                                    ("broader_forward", pred),
                                    ("recorded_zero", pred[pred.recorded_zero])]:
                    saved_daily = daily[(daily.training_arm == arm) & (daily.candidate == candidate)
                                        & (daily.evaluation_month == name) & (daily.scope == scope)]
                    daily_ok &= len(saved_daily) == part.date.nunique()
                    for day, daypart in part.groupby("date"):
                        row = saved_daily[saved_daily.date == day]
                        daily_ok &= len(row) == 1
                        if len(row) == 1:
                            daily_ok &= (len(daypart) == row.iloc[0].n
                                         and np.isclose(mean_absolute_error(daypart.actual_kw,
                                                                            daypart.predicted_kw),
                                                        row.iloc[0].mae_kw, atol=1e-5)
                                         and np.isclose(np.mean(daypart.actual_kw-daypart.predicted_kw),
                                                        row.iloc[0].bias_actual_minus_pred_kw, atol=1e-5))
    check("V6_ALIGN_01", alignment_ok, "Every prediction timestamp, label and scope agrees with compact minute sources")
    check("V6_METRIC_01", metric_ok, "Exact MAE/RMSE/Pearson R/R2/bias recomputed from all 72 saved scopes")
    check("V6_DAILY_01", daily_ok,
          "Daily counts, MAE and bias independently recomputed from end-labelled predictions")
    frozen = json.loads((ROOT / "outputs" / "task3" / "tables" / "frozen_selection.json").read_text())
    baseline = json.loads((OUT / "models" / "jan_jun__baselines.json").read_text())
    check("V6_BASE_01", baseline["train_n"] == frozen["final_fit_n"]
          and np.isclose(baseline["training_mean_kw"], frozen["mean_baseline_kw"], atol=1e-9)
          and np.isclose(baseline["speed_cube_intercept_kw"], frozen["speed_cube"]["intercept_kw"], atol=1e-8)
          and np.isclose(baseline["speed_cube_coefficient_kw_per_kn3"],
                         frozen["speed_cube"]["cubic_kw_per_kn3"], atol=1e-10),
          "Jan-Jun baseline coefficients exactly reproduce V1 frozen baselines")
    old = pd.read_csv(ROOT / "outputs" / "task3" / "tables" / "stress_predictions_metric_audit.csv.gz")
    now = pd.concat([pd.read_csv(OUT / "predictions" /
                                 f"jan_jun__A_hgb_full_v1like__{name}.csv.gz")
                     for name in MONTHS], ignore_index=True)
    check("V6_V1_01", len(now) == len(old) == 52502 and now.window_end_utc.equals(old.window_end_utc)
          and np.array_equal(now.predicted_kw.to_numpy(), old.selected_model.to_numpy())
          and np.allclose(now.actual_kw, old.actual_kw, rtol=0, atol=1e-3),
          "Jan-Jun restricted HGB exactly reproduces archived V1 Sep-Oct predictions")
    old_metrics = pd.read_csv(ROOT / "outputs" / "task3" / "tables" / "stress_metrics.csv")
    baseline_repro = True
    for candidate in ["training_mean", "speed_cubic"]:
        whole = pd.concat([pd.read_csv(OUT / "predictions" /
                                       f"jan_jun__{candidate}__{name}.csv.gz")
                           for name in MONTHS], ignore_index=True)
        for scope, part in [("headline", whole[whole.positive]),
                            ("broader_forward", whole)]:
            reference = old_metrics[(old_metrics.model == candidate) & (old_metrics.scope == scope)].iloc[0]
            baseline_repro &= (len(part) == reference.n
                               and np.isclose(mean_absolute_error(part.actual_kw, part.predicted_kw),
                                              reference.mae_kw, atol=1e-3)
                               and np.isclose(np.sqrt(mean_squared_error(part.actual_kw,
                                                                         part.predicted_kw)),
                                              reference.rmse_kw, atol=1e-3))
    check("V6_V1_02", baseline_repro,
          "Jan-Jun baselines reproduce archived combined Sep-Oct V1 stress metrics")
    manifest_time = (OUT / "experiment_manifest.json").stat().st_mtime_ns
    check("V6_FREEZE_01", manifest_time <= min(p.stat().st_mtime_ns for p in prediction_files)
          and set(MONTHS.values()).isdisjoint(set(sum(ARMS.values(), [])))
          and all(fit.last_training_timestamp.lt("2024-09-01T00:01:00Z")),
          "Manifest predates outputs; evaluation months absent from every fit")
    paired = pd.read_csv(OUT / "paired_training_history_comparison.csv")
    check("V6_PAIR_01", len(paired) == 36 and np.allclose(
          paired["mae_kw__jan_jun_aug"] - paired["mae_kw__jan_jun"],
          paired["delta_aug_minus_janjun__mae_kw"], atol=1e-10),
          "Paired training-history MAE deltas recomputed")
    day_change = pd.read_csv(OUT / "daily_paired_improvement.csv")
    relative = pd.read_csv(OUT / "baseline_relative_comparison.csv")
    check("V6_COMPARE_01", len(relative) == 32 and len(day_change) > 0
          and (day_change.improved_days <= day_change.days_ge30).all()
          and np.allclose(relative.mae_kw - relative.training_mean_mae_kw,
                          relative.mae_minus_training_mean_kw, atol=1e-10)
          and np.allclose(relative.mae_kw - relative.speed_cubic_mae_kw,
                          relative.mae_minus_speed_cubic_kw, atol=1e-10),
          "Baseline-relative and daily paired comparisons are numerical, not rankings")
    with (OUT / "v6_qa.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["check_id", "status", "evidence"])
        w.writeheader()
        w.writerows(checks)
    for item in checks:
        print(item["status"], item["check_id"], item["evidence"])
    failed = [item for item in checks if item["status"] == "FAIL"]
    print(f"{len(checks) - len(failed)} PASS; {len(failed)} FAIL")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
