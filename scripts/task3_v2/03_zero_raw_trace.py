"""Verify representative long zero-power runs directly against raw CSV rows."""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from channel_config import COLUMN_TO_QID

OUT = Path("outputs/task3_v2/phase1")
RAW = Path("data/raw")
DATA = Path("outputs/task3/data")
COLS = ["SHAFT_MechPower_kW", "STW_kn", "ME_RPM_CAMS",
        "ME_FuelLoad_pct", "ME_ScavAirPressure_bar"]
QID_TO_COL = {COLUMN_TO_QID[col]: col for col in COLS}


def main():
    runs = pd.read_csv(OUT / "zero_power_runs_yearwide.csv").head(3)
    chosen = []
    for _, run in runs.iterrows():
        start, end = pd.Timestamp(run.start_utc), pd.Timestamp(run.end_utc)
        middle = start + (end-start)/2
        label = middle.round("min")
        month = label.month
        feature = pd.read_csv(DATA / f"minute_2024_{month:02d}.csv.gz",
                              usecols=["window_end_utc", "target_n", "target_min",
                                       "target_negative_n"]+COLS)
        row = feature[feature.window_end_utc == label.strftime("%Y-%m-%dT%H:%M:%SZ")]
        if len(row) != 1:
            raise ValueError(f"Chosen raw-trace minute not found: {label}")
        row = row.iloc[0]
        chosen.append({"run_start": run.start_utc, "run_minutes": run.minutes,
                       "month": month, "window_end_utc": row.window_end_utc,
                       "minute_prefix": (label-pd.Timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M"),
                       "feature_row": row})
    needed = defaultdict(list)
    for entry in chosen:
        needed[entry["month"]].append(entry)
    observed = defaultdict(list)
    for month, entries in needed.items():
        prefixes = {x["minute_prefix"] for x in entries}
        with (RAW / f"{month}.csv").open(newline="", encoding="utf-8-sig") as file:
            for raw in csv.reader(file):
                if len(raw) >= 3 and raw[1] in QID_TO_COL and raw[0][:16] in prefixes:
                    observed[(month, raw[0][:16], QID_TO_COL[raw[1]])].append((raw[0], float(raw[2])))
    results = []
    for entry in chosen:
        month, prefix, feature = entry["month"], entry["minute_prefix"], entry["feature_row"]
        for col in COLS:
            pairs = observed[(month, prefix, col)]
            values = [value for _, value in pairs]
            raw_mean = np.mean(values) if values else np.nan
            okay = bool(values and abs(raw_mean-float(feature[col])) <= max(.02, abs(raw_mean)*2e-6))
            if col == "SHAFT_MechPower_kW":
                okay &= len(values) == int(feature.target_n)
                okay &= all(value == 0 for value in values)
                okay &= float(feature.target_min) == 0
                okay &= int(feature.target_negative_n) == 0
            results.append({"run_start": entry["run_start"], "run_minutes": entry["run_minutes"],
                            "window_end_utc": entry["window_end_utc"], "column": col,
                            "qid": COLUMN_TO_QID[col], "raw_n": len(values),
                            "raw_mean": raw_mean, "minute_value": feature[col],
                            "raw_min": min(values) if values else np.nan,
                            "raw_max": max(values) if values else np.nan,
                            "first_ts": min(ts for ts, _ in pairs) if pairs else "",
                            "last_ts": max(ts for ts, _ in pairs) if pairs else "",
                            "pass": okay})
    table = pd.DataFrame(results)
    table.to_csv(OUT / "zero_power_raw_trace.csv", index=False)
    print({"checked_runs": len(chosen), "checked_channels": len(table),
           "all_pass": bool(table["pass"].all())})
    if not table["pass"].all():
        raise SystemExit("Raw zero-power trace failed")


if __name__ == "__main__":
    main()
