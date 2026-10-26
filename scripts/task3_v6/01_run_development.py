"""V6: fixed chronological histories, fixed V2 onboard configurations.

Run from project root: python -X utf8 -B scripts/task3_v6/01_run_development.py
Only Jan-Jun and August labels enter fitting. September and October are
previously inspected development evaluations, never fit/calibration inputs.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import runpy
import time
import calendar
from pathlib import Path

for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[name] = "2"

import joblib
import numpy as np
import pandas as pd
import sklearn
from scipy.optimize import nnls
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


ROOT = Path(__file__).resolve().parents[2]
assert Path.cwd().resolve() == ROOT, "Run from the project root"
V2_PATH = ROOT / "scripts" / "task3_v2" / "07_walkforward_experiments.py"
V2 = runpy.run_path(str(V2_PATH))
TARGET = V2["TARGET"]
COLS = V2["COLS"]
load = V2["load"]
mask = V2["mask"]
model_factory = V2["model"]
CANDIDATE_NAMES = ("A_hgb_full_v1like", "B_hgb_full", "B_ridge_full", "B_hgb_broad_full")
CANDIDATES = [c for c in V2["CANDIDATES"] if c["name"] in CANDIDATE_NAMES]
assert tuple(c["name"] for c in CANDIDATES) == CANDIDATE_NAMES
ARMS = {"jan_jun": [1, 2, 3, 4, 5, 6], "jan_jun_aug": [1, 2, 3, 4, 5, 6, 8]}
EVAL = {"september": 9, "october": 10}
assert set(sum(ARMS.values(), []) + list(EVAL.values())) == {1, 2, 3, 4, 5, 6, 8, 9, 10}
OUT = ROOT / "outputs" / "task3_v6"
PRED = OUT / "predictions"
MODELS = OUT / "models"


def score(y: np.ndarray, p: np.ndarray) -> dict:
    y = np.asarray(y, dtype=np.float64)
    p = np.asarray(p, dtype=np.float64)
    assert len(y) == len(p) and len(y) > 0 and np.isfinite(y).all() and np.isfinite(p).all()
    constant_y = np.ptp(y) <= 1e-12
    constant_p = np.ptp(p) <= 1e-10 * max(1., abs(float(np.mean(p))))
    return {"n": len(y), "mae_kw": float(mean_absolute_error(y, p)),
            "rmse_kw": float(np.sqrt(mean_squared_error(y, p))),
            "pearson_r": np.nan if constant_y or constant_p else float(np.corrcoef(y, p)[0, 1]),
            "r2_score": np.nan if len(y) < 2 or constant_y else float(r2_score(y, p)),
            "bias_actual_minus_pred_kw": float(np.mean(y - p)),
            "observed_mean_kw": float(np.mean(y)), "predicted_mean_kw": float(np.mean(p))}


def atomic_csv(frame: pd.DataFrame, path: Path, compression: str | None = None) -> None:
    tmp = path.with_name(path.name + ".tmp")
    frame.to_csv(tmp, index=False, compression=compression)
    os.replace(tmp, path)


def manifest() -> dict:
    return {
        "version": "V6", "evaluation_role": "previously inspected development; not untouched holdout",
        "arms": ARMS, "evaluation_months": EVAL,
        "fixed_candidates": CANDIDATES,
        "candidate_source": str(V2_PATH.relative_to(ROOT)).replace("\\", "/"),
        "candidate_source_sha256": hashlib.sha256(V2_PATH.read_bytes()).hexdigest(),
        "training_window": "full permitted history, no recent-90-day truncation",
        "target_training_scope": "V2 headline or broader-forward as in each candidate",
        "evaluation_scopes": ["positive", "broader_forward", "recorded_zero"],
        "baseline_definitions": {"training_mean": "mean positive train target",
                                 "speed_cubic": "nonnegative least squares: a + b*STW^3 on positive train"},
        "bias_sign": "actual minus predicted",
        "selection": "none; no V6 parameter choice based on September or October metrics",
        "forbidden_months": [7, 11, 12],
        "forbidden_inputs": "Noon, external weather, target and torquemeter predictors",
        "timestamp_rule": "completed one-minute window labelled by end; calendar day=end minus one minute",
        "python": platform.python_version(), "sklearn": sklearn.__version__,
    }


def prepare_output() -> None:
    PRED.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)
    path = OUT / "experiment_manifest.json"
    config = manifest()
    if path.exists():
        assert json.loads(path.read_text(encoding="utf-8")) == config, "Manifest changed: new version required"
    else:
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def fit_baselines(positive_train: pd.DataFrame) -> dict:
    speed = positive_train.STW_kn.to_numpy(dtype=np.float64)
    y = positive_train[TARGET].to_numpy(dtype=np.float64)
    intercept, cubic = nnls(np.column_stack([np.ones(len(speed)), speed ** 3]), y)[0]
    return {"training_mean_kw": float(np.mean(y)),
            "speed_cube_intercept_kw": float(intercept),
            "speed_cube_coefficient_kw_per_kn3": float(cubic),
            "train_n": len(positive_train)}


def create_eval(month: int, frame: pd.DataFrame) -> pd.DataFrame:
    broad = frame.loc[mask(frame, broad=True)].copy().reset_index(drop=True)
    assert len(broad) > 0 and broad.window_end_utc.is_unique
    broad["positive"] = mask(broad).to_numpy(dtype=bool)
    broad["recorded_zero"] = (broad[TARGET].eq(0) & broad.target_negative_n.eq(0)).to_numpy(dtype=bool)
    broad["negative_or_mixed"] = ~(broad.positive | broad.recorded_zero)
    assert (broad.positive.astype(int) + broad.recorded_zero.astype(int)
            + broad.negative_or_mixed.astype(int)).eq(1).all()
    expected_prefix = f"2024-{month:02d}"
    assert broad.window_end_utc.iloc[0].startswith(expected_prefix)
    return broad


def save_prediction(arm: str, candidate: str, month_name: str, broad: pd.DataFrame,
                    predicted: np.ndarray) -> Path:
    path = PRED / f"{arm}__{candidate}__{month_name}.csv.gz"
    result = pd.DataFrame({"window_end_utc": broad.window_end_utc,
                           "actual_kw": broad[TARGET].to_numpy(dtype=np.float64),
                           "predicted_kw": np.asarray(predicted, dtype=np.float64),
                           "positive": broad.positive.to_numpy(dtype=bool),
                           "recorded_zero": broad.recorded_zero.to_numpy(dtype=bool),
                           "negative_or_mixed": broad.negative_or_mixed.to_numpy(dtype=bool)})
    assert result.window_end_utc.is_unique and np.isfinite(result.predicted_kw).all()
    if path.exists():
        old = pd.read_csv(path)
        assert old.window_end_utc.equals(result.window_end_utc)
        assert np.array_equal(old.actual_kw.to_numpy(), result.actual_kw.to_numpy())
        assert np.allclose(old.predicted_kw, result.predicted_kw, rtol=1e-7, atol=1e-5)
    else:
        atomic_csv(result, path, compression="gzip")
    return path


def score_prediction(arm: str, candidate: str, month_name: str,
                     train_n: int, fit_seconds: float, pred_file: Path) -> tuple[list[dict], pd.DataFrame]:
    p = pd.read_csv(pred_file)
    rows = []
    daily = []
    p["date"] = (pd.to_datetime(p.window_end_utc, utc=True) - pd.Timedelta(minutes=1)).dt.date
    assert 1 <= p.date.nunique() <= calendar.monthrange(2024, EVAL[month_name])[1]
    assert all(day.month == EVAL[month_name] for day in p.date.unique())
    for scope, selector in [("positive", p.positive),
                            ("broader_forward", pd.Series(True, index=p.index)),
                            ("recorded_zero", p.recorded_zero)]:
        part = p.loc[selector]
        if len(part) == 0:
            continue
        common = {"training_arm": arm, "candidate": candidate, "evaluation_month": month_name,
                  "scope": scope, "train_n": train_n, "fit_seconds": fit_seconds}
        rows.append({**common, **score(part.actual_kw, part.predicted_kw),
                     "zero_n_in_scope": int(part.recorded_zero.sum()),
                     "negative_or_mixed_n_in_scope": int(part.negative_or_mixed.sum()),
                     "days_with_labels": part.date.nunique()})
        for day, daypart in part.groupby("date", sort=True):
            daily.append({**common, "date": str(day),
                          **score(daypart.actual_kw, daypart.predicted_kw),
                          "zero_n": int(daypart.recorded_zero.sum()),
                          "negative_or_mixed_n": int(daypart.negative_or_mixed.sum())})
    return rows, pd.DataFrame(daily)


def main() -> None:
    prepare_output()  # frozen before evaluation labels are opened
    complete = [OUT / "development_metrics.csv", OUT / "daily_metrics.csv",
                OUT / "fit_inventory.csv", OUT / "paired_training_history_comparison.csv"]
    if all(path.exists() for path in complete) and len(list(PRED.glob("*.csv.gz"))) == 24 \
            and len(list(MODELS.glob("*.joblib"))) == 8:
        print("PASS: existing complete V6 run preserved; use 03_qa.py to verify saved outputs")
        return
    train_frames = {m: load(m) for m in sorted(set(sum(ARMS.values(), [])))}
    evaluations = {name: create_eval(month, load(month)) for name, month in EVAL.items()}
    for arm, months in ARMS.items():
        train_min = min(train_frames[m].window_end_utc.iloc[0] for m in months)
        train_max = max(train_frames[m].window_end_utc.iloc[-1] for m in months)
        for name, valid in evaluations.items():
            assert train_max < valid.window_end_utc.iloc[0], (arm, name, train_max)
        assert train_min.startswith("2024-01")
    coverage = []
    for name, month in EVAL.items():
        broad = evaluations[name]
        coverage.append({"evaluation_month": name, "calendar_month": month,
                         "completed_minutes": len(load(month)),
                         "forward_with_target": len(broad),
                         "positive_n": int(broad.positive.sum()),
                         "recorded_zero_n": int(broad.recorded_zero.sum()),
                         "negative_or_mixed_n": int(broad.negative_or_mixed.sum()),
                         "positive_pct_of_forward": float(100 * broad.positive.mean()),
                         "zero_pct_of_forward": float(100 * broad.recorded_zero.mean())})
    atomic_csv(pd.DataFrame(coverage), OUT / "evaluation_coverage.csv")
    rows = []
    daily_parts = []
    fits = []
    for arm, months in ARMS.items():
        train = pd.concat([train_frames[m] for m in months], ignore_index=True)
        selected_pos = train.loc[mask(train)].copy()
        selected_broad = train.loc[mask(train, broad=True)].copy()
        assert selected_pos.window_end_utc.is_unique and selected_broad.window_end_utc.is_unique
        assert selected_pos.window_end_utc.max() < evaluations["september"].window_end_utc.min()
        baseline = fit_baselines(selected_pos)
        base_path = MODELS / f"{arm}__baselines.json"
        if base_path.exists():
            old = json.loads(base_path.read_text(encoding="utf-8"))
            assert all(np.isclose(old[k], v, rtol=1e-10, atol=1e-9)
                       for k, v in baseline.items())
        else:
            base_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
        print(f"{arm}: {len(selected_pos):,} positive and {len(selected_broad):,} broad training rows", flush=True)
        for name, valid in evaluations.items():
            for candidate, prediction in [
                ("training_mean", np.full(len(valid), baseline["training_mean_kw"], dtype=np.float64)),
                ("speed_cubic", baseline["speed_cube_intercept_kw"] +
                 baseline["speed_cube_coefficient_kw_per_kn3"] *
                 valid.STW_kn.to_numpy(dtype=np.float64) ** 3),
            ]:
                path = save_prediction(arm, candidate, name, valid, prediction)
                r, d = score_prediction(arm, candidate, name, len(selected_pos), 0., path)
                rows.extend(r)
                daily_parts.append(d)
        for candidate in CANDIDATES:
            chosen = selected_broad if candidate["labels"] == "broad" else selected_pos
            cols = COLS[candidate["group"]]
            assert all(not col.startswith("target") and "SHAFT_" not in col for col in cols)
            assert len(chosen) > 5000
            x = chosen[cols].to_numpy(dtype=np.float32)
            y = chosen[TARGET].to_numpy(dtype=np.float32)
            assert np.isfinite(y).all() and not np.isinf(x).any()
            pipeline = model_factory(candidate)
            started = time.perf_counter()
            pipeline.fit(x, y)
            elapsed = time.perf_counter() - started
            model_path = MODELS / f"{arm}__{candidate['name']}.joblib"
            if model_path.exists():
                saved = joblib.load(model_path)
                assert np.allclose(saved.predict(x[:200]), pipeline.predict(x[:200]),
                                   rtol=1e-7, atol=1e-5)
            else:
                tmp = model_path.with_name(model_path.name + ".tmp")
                joblib.dump(pipeline, tmp)
                os.replace(tmp, model_path)
            fits.append({"training_arm": arm, "candidate": candidate["name"],
                         "training_labels": candidate["labels"],
                         "feature_group": candidate["group"], "family": candidate["family"],
                         "train_n": len(chosen), "feature_n": len(cols),
                         "first_training_timestamp": chosen.window_end_utc.min(),
                         "last_training_timestamp": chosen.window_end_utc.max(),
                         "fit_seconds": elapsed})
            for name, valid in evaluations.items():
                prediction = pipeline.predict(valid[cols].to_numpy(dtype=np.float32))
                path = save_prediction(arm, candidate["name"], name, valid, prediction)
                r, d = score_prediction(arm, candidate["name"], name, len(chosen), elapsed, path)
                rows.extend(r)
                daily_parts.append(d)
            atomic_csv(pd.DataFrame(rows), OUT / "development_metrics.csv")
            print(f"{arm} {candidate['name']}: fit {elapsed:.2f}s", flush=True)
    results = pd.DataFrame(rows)
    daily = pd.concat(daily_parts, ignore_index=True)
    atomic_csv(results, OUT / "development_metrics.csv")
    atomic_csv(daily, OUT / "daily_metrics.csv")
    atomic_csv(pd.DataFrame(fits), OUT / "fit_inventory.csv")
    paired = results[results.scope.isin(["positive", "broader_forward", "recorded_zero"])].pivot(
        index=["candidate", "evaluation_month", "scope"], columns="training_arm",
        values=["mae_kw", "rmse_kw", "pearson_r", "r2_score", "bias_actual_minus_pred_kw", "n"])
    paired.columns = [f"{metric}__{arm}" for metric, arm in paired.columns]
    paired = paired.reset_index()
    for metric in ["mae_kw", "rmse_kw", "pearson_r", "r2_score", "bias_actual_minus_pred_kw"]:
        paired[f"delta_aug_minus_janjun__{metric}"] = (
            paired[f"{metric}__jan_jun_aug"] - paired[f"{metric}__jan_jun"])
    atomic_csv(paired, OUT / "paired_training_history_comparison.csv")
    eligible_daily = daily[daily.n.ge(30)]
    stability = eligible_daily.groupby(["training_arm", "candidate", "evaluation_month", "scope"]).agg(
        days_ge30=("date", "nunique"), median_daily_mae_kw=("mae_kw", "median"),
        p90_daily_mae_kw=("mae_kw", lambda x: x.quantile(.9)),
        worst_daily_mae_kw=("mae_kw", "max"),
        median_daily_bias_kw=("bias_actual_minus_pred_kw", "median"),
        worst_abs_daily_bias_kw=("bias_actual_minus_pred_kw", lambda x: x.abs().max()),
        total_zero_n=("zero_n", "sum"), total_n=("n", "sum")
    ).reset_index()
    atomic_csv(stability, OUT / "daily_stability_summary.csv")
    print("PASS: V6 development experiment completed; metrics, daily scores and predictions saved", flush=True)


if __name__ == "__main__":
    main()
