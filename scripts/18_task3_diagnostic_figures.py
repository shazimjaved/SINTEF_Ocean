"""Replot saved December predictions with explicit sample counts and missing bins.

This script performs descriptive grouping only. It does not load the model,
refit, predict or change original figures, metrics or predictions.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path("outputs/task3")
TABLES = ROOT / "tables"
FIGURES = ROOT / "figures"


def annotate_bars(ax, bars, counts):
    for bar, n in zip(bars, counts):
        ax.annotate(f"n={int(n):,}",
                    (bar.get_x() + bar.get_width()/2, bar.get_height()),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8, rotation=0)


def grouped(frame, column, edges, name):
    labels = pd.cut(frame[column], edges, right=False).astype("string").fillna("Missing")
    work = frame.assign(bin=labels)
    result = work.groupby("bin", dropna=False).agg(
        n=("residual_kw", "size"),
        mae_kw=("residual_kw", lambda x: np.abs(x).mean()),
        bias_kw=("residual_kw", "mean")).reset_index()
    order = {str(interval): k for k, interval in enumerate(pd.IntervalIndex.from_breaks(edges, closed="left"))}
    result["sort_order"] = result.bin.map(order).fillna(len(order)).astype(int)
    result = result.sort_values("sort_order").drop(columns="sort_order").reset_index(drop=True)
    result.insert(0, "condition", name)
    if int(result.n.sum()) != len(frame):
        raise ValueError(f"Diagnostic bin loss for {name}")
    return result


def main():
    pred = pd.read_csv(TABLES / "test_predictions.csv.gz")
    extra = pd.read_csv(ROOT / "data/minute_2024_12.csv.gz",
                        usecols=["window_end_utc", "SOG_kn", "HULL_TurnRate_degmin", "WIND_RelSpeed_kn"])
    frame = pred.merge(extra, on="window_end_utc", validate="one_to_one")
    if len(frame) != len(pred):
        raise ValueError("Prediction/feature timestamp join lost rows")
    frame = frame.loc[frame.headline].copy()
    if len(frame) != 39270:
        raise ValueError("Unexpected headline count; original scope must stay fixed")
    frame["abs_turn_degmin"] = frame.HULL_TurnRate_degmin.abs()
    wind = grouped(frame, "WIND_RelSpeed_kn", [0, 5, 10, 15, 20, 30, np.inf], "relative_wind_kn")
    turn = grouped(frame, "abs_turn_degmin", [0, .5, 1, 3, 10, np.inf], "absolute_turn_degmin")
    sog = grouped(frame, "SOG_kn", [0, 3, 5, 7, 9, 11, 13, np.inf], "speed_over_ground_kn")
    conditions = pd.concat([wind, turn, sog], ignore_index=True)
    conditions.to_csv(TABLES / "test_operating_condition_error_audited.csv", index=False)
    missing_wind = int(wind.loc[wind.bin == "Missing", "n"].sum())
    high_turn = int(turn.loc[turn.bin == "[10.0, inf)", "n"].sum())
    coverage = pd.DataFrame([
        {"condition": "relative_wind_kn", "headline_n": len(frame), "binned_n": int(wind.n.sum()),
         "missing_bin_n": missing_wind, "small_high_turn_bin_n": ""},
        {"condition": "absolute_turn_degmin", "headline_n": len(frame), "binned_n": int(turn.n.sum()),
         "missing_bin_n": int(turn.loc[turn.bin == "Missing", "n"].sum()),
         "small_high_turn_bin_n": high_turn},
        {"condition": "speed_over_ground_kn", "headline_n": len(frame), "binned_n": int(sog.n.sum()),
         "missing_bin_n": int(sog.loc[sog.bin == "Missing", "n"].sum()),
         "small_high_turn_bin_n": ""},
    ])
    coverage.to_csv(TABLES / "diagnostic_bin_coverage.csv", index=False)

    frame["date"] = pd.to_datetime(frame.window_end_utc, utc=True).dt.strftime("%Y-%m-%d")
    daily = frame.groupby("date").agg(
        n=("residual_kw", "size"),
        mae_kw=("residual_kw", lambda x: np.abs(x).mean()),
        bias_kw=("residual_kw", "mean")).reset_index()
    if int(daily.n.sum()) != len(frame):
        raise ValueError("Daily bin coverage does not match headline")
    daily.to_csv(TABLES / "test_daily_error_audited.csv", index=False)
    speed = grouped(frame, "STW_kn", [3, 5, 7, 9, 11, 13, 16, 25, np.inf], "speed_through_water_kn")
    speed.to_csv(TABLES / "test_speed_error_audited.csv", index=False)

    FIGURES.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 1, figsize=(10, 6.1), sharex=True,
                             gridspec_kw={"height_ratios": [2, 1]})
    x = np.arange(len(daily))
    axes[0].plot(x, daily.mae_kw, color="#2a788e", marker="o", ms=3, lw=1)
    axes[0].set(ylabel="Daily MAE (kW)", title="December holdout: daily error and eligible sample count")
    bars = axes[1].bar(x, daily.n, color="#7ad151")
    axes[1].set(ylabel="n", xlabel="Day in December")
    axes[1].set_xticks(x, daily.date.str[-2:], rotation=0)
    for bar, n in zip(bars, daily.n):
        axes[1].annotate(str(int(n)), (bar.get_x()+bar.get_width()/2, bar.get_height()),
                         xytext=(0, 2), textcoords="offset points", rotation=90,
                         fontsize=6, ha="center", va="bottom")
    axes[1].set_ylim(0, max(daily.n)*1.3)
    fig.tight_layout()
    fig.savefig(FIGURES / "test_daily_mae_audited.png", dpi=220)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.8))
    bars = ax.bar(speed.bin, speed.mae_kw, color="#35b779")
    annotate_bars(ax, bars, speed.n)
    ax.set_ylim(0, max(speed.mae_kw)*1.2)
    ax.tick_params(axis="x", rotation=35)
    ax.set(xlabel="Speed through water (kn)", ylabel="MAE (kW)",
           title="December holdout error by speed, with bin counts")
    fig.tight_layout()
    fig.savefig(FIGURES / "test_error_vs_speed_audited.png", dpi=220)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(9, 8.2))
    for ax, table, title in [(axes[0], wind, "Relative wind speed (94 missing observations included)"),
                             (axes[1], turn, "Absolute turn rate (highest bin has only eight observations)")]:
        bars = ax.bar(table.bin, table.mae_kw, color="#3b528b")
        annotate_bars(ax, bars, table.n)
        ax.set_ylim(0, max(table.mae_kw)*1.25)
        ax.tick_params(axis="x", rotation=20)
        ax.set(title=title, ylabel="MAE (kW)")
    axes[1].set_xlabel("Observed condition bin")
    fig.tight_layout()
    fig.savefig(FIGURES / "test_operating_condition_error_audited.png", dpi=220)
    plt.close(fig)
    print({"headline_n": len(frame), "relative_wind_missing": missing_wind,
           "high_turn_bin_n": high_turn, "daily_blocks": len(daily)})


if __name__ == "__main__":
    main()
