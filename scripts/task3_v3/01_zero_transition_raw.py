"""Stream selected raw QIDs around long recorded-zero-power episodes.

Diagnostic-only torquemeter channels are intentionally included here to test
whether zero power is accompanied by zero torque/RPM. They remain excluded from
all prediction features. Reads the monthly long CSVs once per needed month.
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from channel_config import COLUMN_TO_QID

OUT = Path("outputs/task3_v3/zero_states")
RUNS = Path("outputs/task3_v2/phase1/zero_power_runs_yearwide.csv")
RAW = Path("data/raw")
COLS = [
    "SHAFT_MechPower_kW", "SHAFT_Torque_Nm_TQ", "SHAFT_RPM_TQ",
    "SHAFT_Revolutions_TQ", "SHAFT_MechEnergy_kWh_TQ",
    "SHAFT_ThrustForce_kN_TQ", "ME_FuelMassFlow_kghr_TQ",
    "ME_RPM_CAMS", "ME_FuelLoad_pct", "ME_ScavAirPressure_bar",
    "ME_TC_RPM_Transducer", "STW_kn", "SOG_kn",
]
QID_TO_COL = {COLUMN_TO_QID[col]: col for col in COLS}
SELECT = [0, 1, 2, 7]  # June, late August, early September, November


def windows(runs):
    assignments = defaultdict(list)
    for i in SELECT:
        run = runs.iloc[i]
        name = f"run_{i+1}_{pd.Timestamp(run.start_utc):%Y%m%d}"
        start, end = pd.Timestamp(run.start_utc), pd.Timestamp(run.end_utc)
        middle = start + (end-start)/2
        for boundary, anchor, before, after in [
            ("start", start, 30, 30),
            ("middle", middle.round("min"), 5, 5),
            ("end", end, 30, 30),
        ]:
            for offset in range(-before, after+1):
                window_end = anchor + pd.Timedelta(minutes=offset)
                source_minute = window_end - pd.Timedelta(minutes=1)
                key = source_minute.strftime("%Y-%m-%dT%H:%M")
                assignments[key].append((name, boundary, offset,
                                         window_end.strftime("%Y-%m-%dT%H:%M:%SZ")))
    return assignments


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    runs = pd.read_csv(RUNS)
    assert len(runs) > max(SELECT)
    selected = windows(runs)
    by_month = defaultdict(set)
    for key in selected:
        by_month[int(key[5:7])].add(key)
    collected = []
    for month, prefixes in sorted(by_month.items()):
        with (RAW / f"{month}.csv").open(newline="", encoding="utf-8-sig") as file:
            for raw in csv.reader(file):
                if len(raw) < 3 or raw[1] not in QID_TO_COL:
                    continue
                prefix = raw[0][:16]
                if prefix not in prefixes:
                    continue
                value = float(raw[2])
                for name, boundary, offset, window_end in selected[prefix]:
                    collected.append((name, boundary, offset, window_end,
                                      raw[0], QID_TO_COL[raw[1]], raw[1], value))
        print(f"scanned raw month {month:02d}", flush=True)
    sample = pd.DataFrame(collected, columns=["episode", "boundary", "offset_min",
                        "window_end_utc", "raw_timestamp", "channel", "qid", "value"])
    assert len(sample) and set(sample.channel) == set(COLS)
    sample.to_csv(OUT / "selected_raw_readings.csv.gz", index=False, compression="gzip")
    minute = sample.groupby(["episode", "boundary", "offset_min", "window_end_utc", "channel"],
                            observed=True).agg(n=("value", "size"), mean=("value", "mean"),
                                               minimum=("value", "min"), maximum=("value", "max"),
                                               first=("value", "first"), last=("value", "last")).reset_index()
    minute.to_csv(OUT / "minute_channel_traces.csv", index=False)
    summary = []
    for (episode, boundary, channel), frame in minute.groupby(["episode", "boundary", "channel"]):
        for phase, subset in [("before10", frame[frame.offset_min.between(-10, -1)]),
                              ("after10", frame[frame.offset_min.between(0, 9)]),
                              ("middle11", frame[frame.offset_min.between(-5, 5)])]:
            if subset.empty:
                continue
            summary.append({"episode": episode, "boundary": boundary, "channel": channel,
                            "phase": phase, "minutes_with_readings": len(subset),
                            "raw_readings": int(subset.n.sum()),
                            "median_of_minute_means": float(subset["mean"].median()),
                            "mean_of_minute_means": float(subset["mean"].mean()),
                            "minimum_raw": float(subset.minimum.min()),
                            "maximum_raw": float(subset.maximum.max())})
    pd.DataFrame(summary).to_csv(OUT / "boundary_channel_summary.csv", index=False)
    transition = []
    for (episode, boundary, channel), group in pd.DataFrame(summary).groupby(
            ["episode", "boundary", "channel"]):
        if boundary == "middle":
            continue
        before = group[group.phase == "before10"]
        after = group[group.phase == "after10"]
        if len(before) != 1 or len(after) != 1:
            continue
        b, a = before.iloc[0], after.iloc[0]
        transition.append({"episode": episode, "boundary": boundary, "channel": channel,
                           "before_median": b.median_of_minute_means,
                           "after_median": a.median_of_minute_means,
                           "delta": a.median_of_minute_means-b.median_of_minute_means,
                           "before_minutes": int(b.minutes_with_readings),
                           "after_minutes": int(a.minutes_with_readings),
                           "before_raw_n": int(b.raw_readings), "after_raw_n": int(a.raw_readings)})
    changes = pd.DataFrame(transition)
    changes.to_csv(OUT / "ten_minute_transitions.csv", index=False)
    plot_channels = ["SHAFT_MechPower_kW", "SHAFT_Torque_Nm_TQ", "SHAFT_RPM_TQ",
                     "ME_RPM_CAMS", "ME_FuelLoad_pct", "STW_kn"]
    for episode in sorted(minute.episode.unique()):
        fig, axs = plt.subplots(len(plot_channels), 2, figsize=(12, 11), sharex="col")
        for col, boundary in enumerate(["start", "end"]):
            for row, channel in enumerate(plot_channels):
                s = minute[(minute.episode == episode) & (minute.boundary == boundary)
                           & (minute.channel == channel)].sort_values("offset_min")
                axs[row, col].plot(s.offset_min, s["mean"], marker=".", markersize=2)
                axs[row, col].axvline(0, color="firebrick", linestyle="--", linewidth=1)
                axs[row, col].set_ylabel(channel.replace("_", " "), fontsize=8)
                axs[row, col].grid(alpha=.2)
            axs[0, col].set_title(f"{episode}: {boundary} of zero run")
            axs[-1, col].set_xlabel("Minutes from recorded-zero boundary")
        fig.tight_layout()
        fig.savefig(OUT / f"{episode}_raw_transitions.png", dpi=160)
        plt.close(fig)
    print({"raw_rows": len(sample), "minute_channel_rows": len(minute),
           "transition_rows": len(changes), "episodes": sample.episode.nunique()})


if __name__ == "__main__":
    main()
