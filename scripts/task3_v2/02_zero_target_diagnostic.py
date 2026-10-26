"""Investigate recorded zero shaft power with positive forward/engine signals.

Descriptive only: thresholds flag implausibility for review, not a diagnosis or
an inference-time filter. No model fitting and no source-data writes.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path("outputs/task3_v2/phase1")
DATA = Path("outputs/task3/data")
TARGET = "SHAFT_MechPower_kW"
COLS = ["window_end_utc", TARGET, "target_n", "target_min", "target_negative_n",
        "STW_kn", "SOG_kn", "ME_RPM_CAMS", "ME_FuelLoad_pct",
        "ME_ScavAirPressure_bar"]


def runs(frame, month):
    # Calendar minute grid is complete. A run stops at every nonzero, missing
    # target, low-speed minute or timestamp gap.
    frame = frame.copy()
    frame["ts"] = pd.to_datetime(frame.window_end_utc, utc=True)
    is_zero_forward = frame.target_n.gt(0) & frame.STW_kn.ge(3) & frame[TARGET].eq(0)
    active = (frame.ME_RPM_CAMS.gt(50) & frame.ME_FuelLoad_pct.gt(20)
              & frame.ME_ScavAirPressure_bar.gt(.5))
    frame["zero_forward"] = is_zero_forward
    frame["active_engine"] = active
    group = (is_zero_forward.ne(is_zero_forward.shift(fill_value=False))
             | frame.ts.diff().ne(pd.Timedelta(minutes=1))).cumsum()
    rows = []
    for _, block in frame[is_zero_forward].groupby(group[is_zero_forward]):
        idx_start, idx_end = block.index[0], block.index[-1]
        before = frame.iloc[idx_start-1][TARGET] if idx_start > 0 else np.nan
        after = frame.iloc[idx_end+1][TARGET] if idx_end+1 < len(frame) else np.nan
        rows.append({"month": month, "start_utc": block.ts.iloc[0], "end_utc": block.ts.iloc[-1],
                     "minutes": len(block), "engine_active_minutes": int(block.active_engine.sum()),
                     "engine_active_pct": 100*block.active_engine.mean(),
                     "stw_median_kn": block.STW_kn.median(),
                     "rpm_median": block.ME_RPM_CAMS.median(),
                     "fuel_load_median_pct": block.ME_FuelLoad_pct.median(),
                     "pressure_median_bar": block.ME_ScavAirPressure_bar.median(),
                     "target_before_kw": before, "target_after_kw": after})
    return pd.DataFrame(rows), is_zero_forward, active


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    monthly, all_runs = [], []
    year_frames = []
    for month in range(1, 13):
        frame = pd.read_csv(DATA / f"minute_2024_{month:02d}.csv.gz", usecols=COLS)
        frame.index = np.arange(len(frame))
        year_frames.append(frame)
        found, zero, active = runs(frame, month)
        all_runs.append(found)
        forward = frame.target_n.gt(0) & frame.STW_kn.ge(3)
        monthly.append({"month": month, "forward_target_minutes": int(forward.sum()),
                        "zero_forward_minutes": int(zero.sum()),
                        "zero_forward_with_active_engine": int((zero & active).sum()),
                        "active_engine_zero_pct": 100*(zero & active).sum()/zero.sum() if zero.any() else np.nan,
                        "zero_runs": len(found), "longest_zero_run_minutes": int(found.minutes.max()) if len(found) else 0,
                        "zero_target_raw_reading_count_min": int(frame.loc[zero,"target_n"].min()) if zero.any() else 0,
                        "zero_target_raw_reading_count_median": float(frame.loc[zero,"target_n"].median()) if zero.any() else np.nan})
    monthly = pd.DataFrame(monthly)
    run_table = pd.concat(all_runs, ignore_index=True).sort_values("minutes", ascending=False)
    year_runs, _, _ = runs(pd.concat(year_frames, ignore_index=True), "all_2024")
    year_runs = year_runs.sort_values("minutes", ascending=False)
    monthly.to_csv(OUT / "zero_power_monthly.csv", index=False)
    run_table.to_csv(OUT / "zero_power_runs.csv", index=False)
    year_runs.to_csv(OUT / "zero_power_runs_yearwide.csv", index=False)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.bar(monthly.month.astype(str), monthly.zero_forward_minutes, color="#31688e")
    for bar, n in zip(bars, monthly.zero_forward_with_active_engine):
        if n:
            ax.annotate(f"active {int(n):,}",
                        (bar.get_x()+bar.get_width()/2, bar.get_height()),
                        xytext=(0,3), textcoords="offset points", fontsize=8, ha="center")
    ax.set(xlabel="2024 month", ylabel="Forward minutes with recorded zero power",
           title="Recorded zero shaft power despite forward speed")
    fig.tight_layout()
    fig.savefig(OUT / "zero_power_forward_monthly.png", dpi=180)
    plt.close(fig)
    print(monthly[["month", "zero_forward_minutes", "zero_forward_with_active_engine",
                   "longest_zero_run_minutes"]].to_string(index=False))
    print("top_runs", year_runs[["start_utc", "end_utc", "minutes", "engine_active_pct"]].head(5).to_dict("records"))


if __name__ == "__main__":
    main()
