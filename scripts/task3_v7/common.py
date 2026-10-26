"""Shared frozen protocol and utilities for V7 conditional experiments."""
from __future__ import annotations

import os
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "2"

import hashlib
import json
import runpy
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import nnls
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT = Path(__file__).resolve().parents[2]
assert Path.cwd().resolve() == ROOT, "Run V7 scripts from project root"
OUT = ROOT / "outputs/task3_v7"
V2_PATH = ROOT / "scripts/task3_v2/07_walkforward_experiments.py"
V2 = runpy.run_path(str(V2_PATH))
TARGET = V2["TARGET"]
COLS = V2["COLS"]
LOAD = V2["load"]
MASK = V2["mask"]
FACTORY = V2["model"]
DEFINITIONS = {c["name"]: c for c in V2["CANDIDATES"]}
FIXED_MONTHS = [1, 2, 3, 4, 5, 6, 8]
MONTHS = [1, 2, 3, 4, 5, 6, 8, 9, 10]
B_MODELS = ["B_ridge_full", "B_hgb_full", "B_hgb_broad_full"]
C_MODELS = ["B_ridge_full", "B_hgb_broad_full"]
C_TRAIN = {4: [1, 2, 3], 5: [1, 2, 3, 4], 6: [1, 2, 3, 4, 5],
           8: [1, 2, 3, 4, 5, 6], 9: FIXED_MONTHS,
           10: FIXED_MONTHS + [9]}
DAY_STARTS = [3, 6, 9, 12, 15, 18, 21, 24, 27]
GAP_HOURS = [1, 6, 24] * 3
LAG = pd.Timedelta(hours=24)
LOOKBACK = pd.Timedelta(days=3)
MIN_HISTORY = 30


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def csv_write(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, compression="gzip" if path.name.endswith(".gz") else None)


def ts(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame.window_end_utc, utc=True)


def day_of(frame: pd.DataFrame) -> pd.Series:
    # Minute (t-1min,t] belongs to its covered calendar date.
    return (ts(frame) - pd.Timedelta(minutes=1)).dt.floor("D")


def eligible(frame: pd.DataFrame) -> pd.Series:
    """Operational eligibility has no dependency on the current target."""
    return frame.STW_kn.notna() & np.isfinite(frame.STW_kn) & frame.STW_kn.ge(3)


def observed(frame: pd.DataFrame) -> pd.Series:
    return frame.target_n.gt(0) & frame[TARGET].notna() & np.isfinite(frame[TARGET])


def positive(frame: pd.DataFrame) -> pd.Series:
    return observed(frame) & frame[TARGET].gt(0) & frame.target_min.ge(0) & frame.target_negative_n.eq(0)


def metric(y, p) -> dict:
    y = np.asarray(y, dtype=np.float64)
    p = np.asarray(p, dtype=np.float64)
    assert len(y) == len(p) and len(y) > 0 and np.isfinite(y).all() and np.isfinite(p).all()
    cy = np.ptp(y) <= 1e-12
    cp = np.ptp(p) <= 1e-10 * max(1., abs(float(np.mean(p))))
    # sklearn's finite convention returns 0 for an imperfect constant-target
    # subset. Preserve that exact result and mark its scientific degeneracy.
    return {"n": len(y), "mae_kw": float(mean_absolute_error(y, p)),
            "rmse_kw": float(np.sqrt(mean_squared_error(y, p))),
            "r2_score": float(r2_score(y, p)) if len(y) > 1 else np.nan,
            "pearson_r": np.nan if cy or cp or len(y) < 2 else float(np.corrcoef(y, p)[0, 1]),
            "bias_actual_minus_pred_kw": float(np.mean(y - p)),
            "constant_target": cy, "actual_mean_kw": float(np.mean(y)),
            "predicted_mean_kw": float(np.mean(p))}


def baselines(frame: pd.DataFrame) -> dict:
    d = frame.loc[eligible(frame) & positive(frame)]
    y = d[TARGET].to_numpy(dtype=np.float64)
    x = d.STW_kn.to_numpy(dtype=np.float64)
    a, b = nnls(np.column_stack([np.ones(len(x)), x ** 3]), y)[0]
    return {"mean_kw": float(np.mean(y)), "intercept_kw": float(a), "cube_kw_per_kn3": float(b),
            "train_n": len(d), "max_label_ts": d.window_end_utc.max()}


def base_predict(frame: pd.DataFrame, spec: dict) -> dict[str, np.ndarray]:
    return {"mean": np.full(len(frame), spec["mean_kw"]),
            "speed_cubic": spec["intercept_kw"] + spec["cube_kw_per_kn3"] * frame.STW_kn.to_numpy(float) ** 3}


def training(frame: pd.DataFrame, candidate: str, cutoff: pd.Timestamp) -> pd.DataFrame:
    ok = eligible(frame) & observed(frame) & ts(frame).lt(cutoff)
    if DEFINITIONS[candidate]["labels"] != "broad":
        ok &= positive(frame)
    return frame.loc[ok].copy()


def schedule() -> pd.DataFrame:
    rows = []
    for month in C_TRAIN:
        for i, (day, hours) in enumerate(zip(DAY_STARTS, GAP_HOURS), 1):
            start = pd.Timestamp(2024, month, day, 6, tz="UTC")
            end = start + pd.Timedelta(hours=hours)
            rows.append({"block_id": f"m{month:02d}_b{i:02d}_{hours}h", "month": month,
                         "duration_hours": hours, "start_utc": start.isoformat(),
                         "end_utc": end.isoformat(), "calendar_minutes": hours * 60})
    return pd.DataFrame(rows)


def hidden_mask(frame: pd.DataFrame, blocks: pd.DataFrame) -> np.ndarray:
    t = ts(frame)
    out = np.zeros(len(frame), dtype=bool)
    for r in blocks.itertuples():
        out |= (t.gt(pd.Timestamp(r.start_utc)) & t.le(pd.Timestamp(r.end_utc))).to_numpy()
    return out


def seal_targets(frame: pd.DataFrame, hide: np.ndarray) -> pd.DataFrame:
    result = frame.copy()
    result.loc[hide, TARGET] = np.nan
    result.loc[hide, "target_min"] = np.nan
    result.loc[hide, "target_n"] = 0
    result.loc[hide, "target_negative_n"] = 0
    result["artificially_hidden"] = hide
    return result


def output_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame({"window_end_utc": frame.window_end_utc,
                           "actual_kw": frame[TARGET].to_numpy(dtype=np.float64),
                           "operational_eligible": eligible(frame).to_numpy(),
                           "observed_truth": observed(frame).to_numpy(),
                           "positive": positive(frame).to_numpy(),
                           "recorded_zero": (observed(frame) & frame[TARGET].eq(0)
                                             & frame.target_negative_n.eq(0)).to_numpy()})
    result["negative_or_mixed"] = result.observed_truth & ~(result.positive | result.recorded_zero)
    return result


def daily_history(history: pd.DataFrame, prediction_frame: pd.DataFrame,
                  base_columns: list[str], fallback_mean: float, positive_only: bool = False):
    """Compute daily residual offsets and matched-history baselines.

    history contains only visible out-of-training-period labels and fixed base
    predictions. No gap truth is admitted. All methods use [day-4d,day-1d).
    """
    h = history.loc[history.operational_eligible & history.observed_truth].copy()
    if positive_only:
        h = h.loc[h.positive]
    h["ts"] = ts(h)
    pday = day_of(prediction_frame)
    offsets = {c: np.zeros(len(prediction_frame), dtype=np.float64) for c in base_columns}
    persist = np.full(len(prediction_frame), fallback_mean, dtype=np.float64)
    means = persist.copy()
    ledger = []
    for day in pday.unique():
        day = pd.Timestamp(day)
        cutoff = day - LAG
        start = cutoff - LOOKBACK
        pool = h.loc[h.ts.ge(start) & h.ts.lt(cutoff)].sort_values("ts")
        mask_day = pday.eq(day).to_numpy()
        n = len(pool)
        use = n >= MIN_HISTORY
        record = {"prediction_day_utc": day.isoformat(), "history_start_utc": start.isoformat(),
                  "history_cutoff_exclusive_utc": cutoff.isoformat(), "history_n": n,
                  "first_history_ts": pool.window_end_utc.iloc[0] if n else "",
                  "last_history_ts": pool.window_end_utc.iloc[-1] if n else "",
                  "used_history": use, "positive_history_only": positive_only,
                  "prediction_rows": int(mask_day.sum())}
        for c in base_columns:
            offset = float(np.median(pool.actual_kw - pool[c])) if use else 0.
            offsets[c][mask_day] = offset
            record[f"offset__{c}"] = offset
        if use:
            persist[mask_day] = float(pool.actual_kw.iloc[-1])
            means[mask_day] = float(pool.actual_kw.mean())
        record["persistence_kw"] = float(pool.actual_kw.iloc[-1]) if use else fallback_mean
        record["history_mean_kw"] = float(pool.actual_kw.mean()) if use else fallback_mean
        ledger.append(record)
    return offsets, persist, means, pd.DataFrame(ledger)


def protocol() -> dict:
    return {"version": "V7", "B_fixed_months": FIXED_MONTHS, "B_eval_months": [9, 10],
            "B_models": B_MODELS, "C_models": C_MODELS,
            "C_training_months": {str(k): v for k, v in C_TRAIN.items()},
            "quarantined": [7, 11], "December": "previously inspected; never opened in V7",
            "source_V2_sha256": digest(V2_PATH),
            "latency_hours": 24, "refresh": "UTC day start; history timestamp strictly < day_start-24h",
            "history_lookback_days": 3, "min_history": MIN_HISTORY,
            "B_update_snapshot": "2024-10-01T00:00:00Z",
            "B_update_label_cutoff_exclusive": "2024-09-30T00:00:00Z",
            "history_scope": "observed STW>=3, includes recorded zeros and negative labels; conditional trust",
            "positive_history_sensitivity": "Ridge only; historical positive labels, never current eligibility",
            "history_fallback": "fixed prediction for residual; positive training mean for persistence/history mean",
            "eligibility": "finite observed onboard STW>=3; independent of current target",
            "scoring": "only previously observed hidden/ordinary target; missing truths never scored as zero",
            "C_schedule": "days 3,6,9,12,15,18,21,24,27 at 06:00 UTC; 1,6,24h repeated; no value-based selection",
            "C_interval": "target window_end > start and <= end",
            "C_global_mask": "all 54 gaps permanently hidden from every reconstruction fit and history",
            "C_calibration_history": "current evaluation month only, out-of-time base residuals",
            "B_calibration_history": "Sep onward only, out-of-time fixed residuals; October can use September",
            "models": {name: DEFINITIONS[name] for name in B_MODELS},
            "features": COLS, "selection": "none; frozen settings; all blocks reported",
            "conditional": "trustworthy labels and 24h latency unverified",
            "evaluation_status": "development only; Sep/Oct previously inspected"}


def prepare() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "experiment_manifest.json"
    expected = protocol()
    if path.exists():
        assert json.loads(path.read_text(encoding="utf-8")) == expected, "Manifest changed; new version required"
    else:
        path.write_text(json.dumps(expected, indent=2), encoding="utf-8")
        csv_write(schedule(), OUT / "reconstruction_blocks.csv")


if __name__ == "__main__":
    prepare()
    print("PASS: V7 protocol and 54 deterministic nonoverlapping blocks frozen")
