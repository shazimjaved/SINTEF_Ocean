"""Post-holdout descriptive diagnostics; never refits or predicts a model."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

TABLES = Path("outputs/task3/tables")
FIGURES = Path("outputs/task3/figures")


def correct_constant_baseline_r():
    # A repeated floating-point mean may have a nonzero numerical std despite
    # being exactly constant. Its Pearson R is mathematically undefined.
    for name in ["validation_model_comparison.csv", "stress_metrics.csv", "test_metrics.csv"]:
        path = TABLES / name
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames
            rows = list(reader)
        for row in rows:
            if row.get("model", row.get("family")) == "training_mean":
                row["pearson_r"] = ""
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)


def main():
    correct_constant_baseline_r()
    pred = pd.read_csv(TABLES / "test_predictions.csv.gz")
    conditions = pd.read_csv("outputs/task3/data/minute_2024_12.csv.gz",
                             usecols=["window_end_utc", "SOG_kn", "HULL_TurnRate_degmin",
                                      "WIND_RelSpeed_kn"])
    joined = pred.merge(conditions, on="window_end_utc", validate="one_to_one")
    if len(joined) != len(pred):
        raise ValueError("December diagnostic join lost predictions")
    selected = joined.loc[joined.headline].copy()
    selected["abs_error_kw"] = selected.residual_kw.abs()
    selected["abs_turn_degmin"] = selected.HULL_TurnRate_degmin.abs()
    definitions = {
        "relative_wind_kn": ("WIND_RelSpeed_kn", [0, 5, 10, 15, 20, 30, np.inf]),
        "absolute_turn_degmin": ("abs_turn_degmin", [0, .5, 1, 3, 10, np.inf]),
        "speed_over_ground_kn": ("SOG_kn", [0, 3, 5, 7, 9, 11, 13, np.inf]),
    }
    rows = []
    for condition, (column, bins) in definitions.items():
        groups = pd.cut(selected[column], bins=bins, right=False)
        for label, frame in selected.groupby(groups, observed=True):
            rows.append({"condition": condition, "bin": str(label), "n": len(frame),
                         "mae_kw": frame.abs_error_kw.mean(),
                         "bias_kw": frame.residual_kw.mean()})
    result = pd.DataFrame(rows)
    result.to_csv(TABLES / "test_operating_condition_error.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, condition, title in [(axes[0], "relative_wind_kn", "Relative wind speed"),
                                 (axes[1], "absolute_turn_degmin", "Absolute turn rate")]:
        subset = result[result.condition == condition]
        ax.bar(subset.bin, subset.mae_kw, color="#3b528b")
        ax.tick_params(axis="x", rotation=40)
        ax.set(title=title, xlabel="Bin", ylabel="December MAE (kW)")
    fig.suptitle("Holdout error across observed operating conditions")
    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / "test_operating_condition_error.png", dpi=220)
    plt.close(fig)
    distribution = {
        "n": int(len(selected)), "actual_mean_kw": float(selected.SHAFT_MechPower_kW.mean()),
        "actual_std_kw": float(selected.SHAFT_MechPower_kW.std()),
        "predicted_mean_kw": float(selected.prediction_kw.mean()),
        "predicted_std_kw": float(selected.prediction_kw.std()),
        "mean_residual_kw": float(selected.residual_kw.mean()),
    }
    pd.DataFrame([distribution]).to_csv(TABLES / "test_distribution_diagnostic.csv", index=False)
    print("Diagnostic rows", len(result), distribution)


if __name__ == "__main__":
    main()
