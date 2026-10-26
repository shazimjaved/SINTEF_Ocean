"""Bounded V8 protocol; fixed definitions, no December/quarantine fitting."""
from __future__ import annotations

import os
for key in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
    os.environ[key] = "2"
import runpy
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
assert Path.cwd().resolve() == ROOT
V7 = runpy.run_path(str(ROOT / "scripts/task3_v7/common.py"))
OUT = ROOT / "outputs/task3_v8"
OLD = ROOT / "outputs/task3_v7"
LOAD, TARGET, COLS = V7["LOAD"], V7["TARGET"], V7["COLS"]
ELIGIBLE, OBSERVED, POSITIVE = V7["eligible"], V7["observed"], V7["positive"]
TS, DAY, METRIC = V7["ts"], V7["day_of"], V7["metric"]
WRITE, DIGEST = V7["csv_write"], V7["digest"]
TRAINING, FACTORY = V7["training"], V7["FACTORY"]
DEFINITION = V7["DEFINITIONS"]["B_ridge_full"]
FEATURES = ["STW_kn", "ME_RPM_CAMS", "ME_FuelLoad_pct", "ME_ScavAirPressure_bar"]
MONTHS = [1, 2, 3, 4, 5, 6, 8, 9, 10]
FOLDS = {6: [1,2,3,4,5], 8: [1,2,3,4,5,6],
         9: [1,2,3,4,5,6,8], 10: [1,2,3,4,5,6,8,9]}
CASES = ["m06_b04_1h", "m06_b06_24h", "m08_b09_24h", "m09_b04_1h"]
METHODS = ["fixed_ridge", "v7_calibrated", "bounded_residual", "clipped_v7",
           "delayed_persistence", "delayed_history_mean", "training_mean", "speed_cubic"]


def anchors() -> pd.DataFrame:
    rows = []
    for month in FOLDS:
        for day in [4,11,20,29]:
            start = pd.Timestamp(2024,month,day,6,tz="UTC")
            rows.append({"anchor_id": f"m{month:02d}_d{day:02d}", "month": month,
                         "start_utc": start.isoformat(), "end_utc": (start+pd.Timedelta(hours=24)).isoformat()})
    return pd.DataFrame(rows)


def protocol() -> dict:
    return {"version":"V8", "earlier_threshold_development":[4,5],
            "feature_scale_months":[1,2,3], "paired_evaluation_months":list(FOLDS),
            "paired_training_months":{str(k):v for k,v in FOLDS.items()},
            "anchor_days":[4,11,20,29], "anchor_hour_utc":6, "horizons_hours":[1,6,24],
            "paired_rule":"one 24h sealed union per anchor; horizons are identical-prefix scores; anchor unions do not overlap",
            "global_embargo":"all 16 maximum-horizon gaps hidden from all later fits/history; no horizons revealed",
            "latency":"history timestamps strictly before covered_day_start-24h; daily refresh",
            "window":"[window_end-1min, window_end), not an intra-window forecast",
            "label_scope":"observed STW>=3 history including zero/negative under conditional trust",
            "history_days":3,"minimum_history":30,
            "threshold_levels":{"offset_abs_cap":0.95,"risk_feature_limits":0.99,"reference_absolute_error":0.95},
            "point_rules":["unchanged V7 median residual", "symmetric cap at early-fold q95(abs daily offset)",
                           "nonnegative V7 clipping as separate output constraint"],
            "flag_only":"no history OR historical zero/negative proportion, residual MAD, stale-label gap, onboard drift or prediction disagreement > early q99",
            "uncertainty_reference":"V7 prediction +/- early-fold q95 absolute error; diagnostic, no guaranteed coverage",
            "current_target":"never used for eligibility, flags, correction, threshold selection or imputation",
            "paired_model":"only V2 B_ridge_full; alpha100; refit for new global embargo, V7 weights unchanged",
            "no_tuning_using":[6,8,9,10,12],"quarantine":[7,11],"December":"not read",
            "selection":"no final model promotion; compare coverage, transitions, ordinary/zero errors, tails and matched baselines",
            "source_v7_common_sha256":DIGEST(ROOT/"scripts/task3_v7/common.py"),
            "source_v2_sha256":DIGEST(V7["V2_PATH"])}


def prepare():
    OUT.mkdir(exist_ok=True)
    path = OUT/"experiment_manifest.json"
    if path.exists():
        assert json.loads(path.read_text()) == protocol(), "Frozen V8 protocol differs"
    else:
        path.write_text(json.dumps(protocol(),indent=2),encoding="utf-8")
        WRITE(anchors(),OUT/"paired_anchors.csv")


def load_v7_history(month: int) -> pd.DataFrame:
    h = pd.read_csv(OLD/f"reconstruction/visible_history_m{month:02d}.csv.gz",
                    dtype={"fixed__B_ridge_full":"float32"}, low_memory=False)
    h["fixed_ridge"] = h["fixed__B_ridge_full"].astype(float)
    h["v7_calibrated"] = h["calibrated__B_ridge_full"]
    d = LOAD(month)
    assert h.window_end_utc.equals(d.window_end_utc)
    for c in FEATURES:
        h[c] = d[c].to_numpy(dtype=float)
    return h


def history_stats(history: pd.DataFrame, prediction: pd.DataFrame, fallback: float):
    """Admitted history only; no current-truth access in any returned statistic."""
    h = history.loc[history.operational_eligible & history.observed_truth].copy()
    h["_time"] = TS(h)
    days = DAY(prediction)
    result = prediction.copy()
    ledgers = []
    for day in days.unique():
        day = pd.Timestamp(day)
        cutoff = day-pd.Timedelta(hours=24)
        pool = h[h._time.ge(cutoff-pd.Timedelta(days=3)) & h._time.lt(cutoff)].sort_values("_time")
        n = len(pool); used = n>=30
        residual = pool.actual_kw-pool.fixed_ridge
        median = float(residual.median()) if used else 0.
        rec = {"prediction_day_utc":day.isoformat(),"history_cutoff_exclusive_utc":cutoff.isoformat(),
               "history_n":n,"history_used":used,"offset_kw":median,
               "residual_mad_kw":float((residual-residual.median()).abs().median()) if used else np.nan,
               "zero_fraction":float(pool.recorded_zero.mean()) if n else np.nan,
               "positive_fraction":float(pool.positive.mean()) if n else np.nan,
               "negative_fraction":float(pool.negative_or_mixed.mean()) if n else np.nan,
               "last_admitted_label_utc":pool.window_end_utc.iloc[-1] if n else "",
               "last_admitted_power_kw":float(pool.actual_kw.iloc[-1]) if n else np.nan,
               "cutoff_to_last_label_hours":float((cutoff-pool._time.iloc[-1]).total_seconds()/3600) if n else np.nan,
               "persistence_kw":float(pool.actual_kw.iloc[-1]) if used else fallback,
               "history_mean_kw":float(pool.actual_kw.mean()) if used else fallback}
        for c in FEATURES:
            rec[f"history_median__{c}"] = float(pool[c].median()) if n else np.nan
        selected = days.eq(day)
        for c,v in rec.items():
            result.loc[selected,c] = v
        ledgers.append(rec)
    result["v7_calibrated"] = result.fixed_ridge+result.offset_kw
    result["delayed_persistence"] = result.persistence_kw
    result["delayed_history_mean"] = result.history_mean_kw
    result["label_age_hours"] = (TS(result)-pd.to_datetime(result.last_admitted_label_utc,utc=True,errors="coerce")).dt.total_seconds()/3600
    result["correction_age_hours"] = (TS(result)-pd.to_datetime(result.prediction_day_utc,utc=True)).dt.total_seconds()/3600
    return result,pd.DataFrame(ledgers)


def reliability_features(frame: pd.DataFrame, scales: dict) -> pd.DataFrame:
    d = frame.copy()
    distances = []
    for c in FEATURES:
        distances.append(((d[c]-d[f"history_median__{c}"])/scales[c]).to_numpy(float)**2)
    d["onboard_history_drift"] = np.sqrt(np.mean(distances,axis=0))
    d["prediction_disagreement_kw"] = (d.v7_calibrated-d.delayed_persistence).abs()
    return d


def apply_rules(frame: pd.DataFrame, thresholds: dict) -> pd.DataFrame:
    d = reliability_features(frame,thresholds["feature_iqr"])
    d["bounded_residual"] = d.fixed_ridge+d.offset_kw.clip(-thresholds["offset_cap_kw"],thresholds["offset_cap_kw"])
    d["clipped_v7"] = d.v7_calibrated.clip(lower=0)
    reasons = {
        "no_history":~d.history_used.astype(bool),
        "historical_zero":d.zero_fraction.gt(thresholds["limits"]["zero_fraction"]),
        "historical_negative":d.negative_fraction.gt(thresholds["limits"]["negative_fraction"]),
        "stale_label":d.cutoff_to_last_label_hours.gt(thresholds["limits"]["cutoff_to_last_label_hours"]),
        "residual_variability":d.residual_mad_kw.gt(thresholds["limits"]["residual_mad_kw"]),
        "onboard_drift":d.onboard_history_drift.gt(thresholds["limits"]["onboard_history_drift"]),
        "prediction_disagreement":d.prediction_disagreement_kw.gt(thresholds["limits"]["prediction_disagreement_kw"]),
        "missing_onboard":d[FEATURES].isna().any(axis=1)}
    for name, flag in reasons.items():
        d[f"flag__{name}"] = flag
    d["abstain"] = np.logical_or.reduce([x.to_numpy(bool) for x in reasons.values()])
    d["reference_interval_low_kw"] = d.v7_calibrated-thresholds["reference_error_kw"]
    d["reference_interval_high_kw"] = d.v7_calibrated+thresholds["reference_error_kw"]
    return d


def scopes(frame: pd.DataFrame):
    main=frame.operational_eligible & frame.observed_truth
    return {"broader_forward":main,"positive":main & frame.positive,
            "recorded_zero":main & frame.recorded_zero,"negative_or_mixed":main & frame.negative_or_mixed}


if __name__ == "__main__":
    prepare()
    print("PASS: frozen V8 protocol, 16 nonoverlapping 24h anchor unions and 3 paired horizons")
