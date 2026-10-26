"""Evaluate a frozen Task 3 model on coverage stress and December once.

The frozen selection file must exist before this program will read December.
An existing December prediction file prevents accidental repeat evaluation.
"""
import json
import runpy
import time
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from channel_config import ANGLE_COLUMNS, COLUMN_TO_SOURCE, MODEL_CANDIDATES, TARGET

TABLES = Path("outputs/task3/tables")
FIGURES = Path("outputs/task3/figures")
MODEL = Path("outputs/task3/models/selected_pipeline.joblib")
COMMON = runpy.run_path("scripts/12_task3_train_validate.py")
load_months = COMMON["load_months"]
label_mask = COMMON["label_mask"]
metrics = COMMON["metrics"]
speed_cube = COMMON["speed_cube"]
WEATHER = sorted(c for c in MODEL_CANDIDATES if COLUMN_TO_SOURCE[c].startswith("provider_"))
WEATHER_COLUMNS = [f"sin__{c}" if c in ANGLE_COLUMNS else c for c in WEATHER]


def evaluate_period(frame, split, pipeline, cols, frozen):
    broad = frame.loc[label_mask(frame, broad=True)].copy()
    selected = label_mask(broad)
    if broad.empty or not selected.any():
        raise ValueError(f"No usable labels in {split}")
    broad["prediction_kw"] = pipeline.predict(broad[cols].to_numpy(dtype=np.float32))
    broad["mean_baseline_kw"] = frozen["mean_baseline_kw"]
    broad["speed_cube_kw"] = speed_cube(broad, frozen["speed_cube"])
    broad["headline"] = selected.to_numpy()
    broad["residual_kw"] = broad[TARGET] - broad.prediction_kw
    broad["weather_all14_fresh"] = broad[WEATHER_COLUMNS].notna().all(axis=1)
    broad["weather_any_fresh"] = broad[WEATHER_COLUMNS].notna().any(axis=1)
    rows = []
    for scope, subset in [("headline", broad.loc[broad.headline]),
                          ("broader_forward", broad)]:
        for name, prediction in [("selected_model", "prediction_kw"),
                                 ("training_mean", "mean_baseline_kw"),
                                 ("speed_cubic", "speed_cube_kw")]:
            rows.append({"split": split, "scope": scope, "model": name,
                         **metrics(subset[TARGET], subset[prediction]),
                         "completed_minutes": len(frame),
                         "target_minutes": int((frame.target_n > 0).sum()),
                         "forward_with_target": len(broad),
                         "headline_minutes": int(broad.headline.sum())})
    return broad, rows


def save_figures(test):
    FIGURES.mkdir(parents=True, exist_ok=True)
    selected = test.loc[test.headline].copy()
    selected["date"] = pd.to_datetime(selected.window_end_utc, utc=True).dt.date
    fig, ax = plt.subplots(figsize=(6.5, 5.8))
    h = ax.hexbin(selected[TARGET], selected.prediction_kw, gridsize=65,
                  mincnt=1, bins="log", cmap="viridis")
    low = min(selected[TARGET].min(), selected.prediction_kw.min())
    high = max(selected[TARGET].max(), selected.prediction_kw.max())
    ax.plot([low, high], [low, high], "k--", lw=1, label="Equality")
    ax.set(xlabel="Observed shaft power (kW)", ylabel="Predicted shaft power (kW)",
           title="December 2024 holdout: forward underway subset")
    fig.colorbar(h, ax=ax, label="log10(count)")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(FIGURES / "test_prediction_vs_actual.png", dpi=220)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(selected.residual_kw, bins=80, color="#31688e", edgecolor="none")
    ax.axvline(0, color="black", lw=1)
    ax.set(xlabel="Observed minus predicted (kW)", ylabel="Completed minutes",
           title="December holdout residual distribution")
    fig.tight_layout()
    fig.savefig(FIGURES / "test_residual_distribution.png", dpi=220)
    plt.close(fig)

    daily = selected.groupby("date").agg(n=("residual_kw", "size"),
              mae_kw=("residual_kw", lambda x: np.mean(np.abs(x))),
              bias_kw=("residual_kw", "mean")).reset_index()
    daily.to_csv(TABLES / "test_daily_error.csv", index=False)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(daily.date.astype(str), daily.mae_kw, marker="o", ms=3, lw=1)
    ax.tick_params(axis="x", rotation=55)
    ax.set(xlabel="December day", ylabel="Daily MAE (kW)",
           title="December holdout error by day")
    fig.tight_layout()
    fig.savefig(FIGURES / "test_daily_mae.png", dpi=220)
    plt.close(fig)

    bins = [3, 5, 7, 9, 11, 13, 16, 25, np.inf]
    selected["speed_bin_kn"] = pd.cut(selected.STW_kn, bins=bins, right=False)
    speed = selected.groupby("speed_bin_kn", observed=True).agg(
        n=("residual_kw", "size"),
        mae_kw=("residual_kw", lambda x: np.mean(np.abs(x))),
        bias_kw=("residual_kw", "mean")).reset_index()
    speed["speed_bin_kn"] = speed.speed_bin_kn.astype(str)
    speed.to_csv(TABLES / "test_speed_error.csv", index=False)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(speed.speed_bin_kn, speed.mae_kw, color="#35b779")
    ax.tick_params(axis="x", rotation=35)
    ax.set(xlabel="Speed through water (kn)", ylabel="MAE (kW)",
           title="December holdout error by speed")
    fig.tight_layout()
    fig.savefig(FIGURES / "test_error_vs_speed.png", dpi=220)
    plt.close(fig)
    return selected, daily, speed


def main():
    frozen_path = TABLES / "frozen_selection.json"
    output = TABLES / "test_predictions.csv.gz"
    if output.exists():
        raise FileExistsError("December predictions already exist; holdout must not be re-evaluated for tuning")
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    bundle = joblib.load(MODEL)
    if bundle["frozen"] != frozen:
        raise ValueError("Frozen selection and model metadata differ")
    pipeline = bundle["pipeline"]
    cols = bundle["columns"]
    TABLES.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    stress = load_months([9, 10])
    stress_pred, stress_rows = evaluate_period(stress, "sep_oct_coverage_stress", pipeline, cols, frozen)
    pd.DataFrame(stress_rows).to_csv(TABLES / "stress_metrics.csv", index=False)
    # Only after selection, model fitting and stress outputs have been fixed is
    # December opened. The entire December evaluation is run exactly once.
    test = load_months([12])
    test_pred, test_rows = evaluate_period(test, "december_holdout", pipeline, cols, frozen)
    report_cols = ["window_end_utc", TARGET, "STW_kn", "target_n", "target_negative_n",
                   "target_min", "prediction_kw", "mean_baseline_kw", "speed_cube_kw",
                   "residual_kw", "headline", "weather_all14_fresh", "weather_any_fresh"]
    test_pred[report_cols].to_csv(output, index=False, compression="gzip")
    pd.DataFrame(test_rows).to_csv(TABLES / "test_metrics.csv", index=False)
    selected, daily, speed = save_figures(test_pred)
    weather = []
    for split, frame in [("stress", stress_pred), ("test", test_pred)]:
        for scope, subset in [("headline", frame.loc[frame.headline]),
                              ("broader_forward", frame)]:
            weather.append({"split": split, "scope": scope, "n": len(subset),
                            "all14_fresh_pct": 100 * subset.weather_all14_fresh.mean(),
                            "any_fresh_pct": 100 * subset.weather_any_fresh.mean()})
    pd.DataFrame(weather).to_csv(TABLES / "weather_availability_sensitivity.csv", index=False)
    diagnostics = {"eval_seconds": round(time.perf_counter() - started, 2),
                   "holdout_rows": len(test), "headline_n": len(selected),
                   "daily_blocks": len(daily), "speed_bins": len(speed),
                   "residual_quantiles_kw": {str(q): float(selected.residual_kw.quantile(q))
                                            for q in [.01, .05, .25, .5, .75, .95, .99]}}
    (TABLES / "test_diagnostics.json").write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
    print("DECEMBER", test_rows, diagnostics, flush=True)


if __name__ == "__main__":
    main()
