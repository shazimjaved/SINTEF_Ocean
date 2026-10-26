"""Focused July/November target-quality evidence; no automatic row deletion."""

import csv
from pathlib import Path
import numpy as np
import pandas as pd
from channel_config import COLUMN_TO_QID

RAW = Path("data/raw")
OUT = Path("outputs/tables")
NAMES = ["SHAFT_MechPower_kW", "ME_RPM_CAMS", "STW_kn"]
SELECT = {COLUMN_TO_QID[name]: name for name in NAMES}


def load_selected(month):
    rows = {name: [] for name in NAMES}
    with (RAW / f"{month}.csv").open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) < 3 or row[1] not in SELECT:
                continue
            rows[SELECT[row[1]]].append((row[0], float(row[2])))
    series = {}
    for name, values in rows.items():
        ts = pd.to_datetime([v[0] for v in values], utc=True).tz_localize(None)
        series[name] = pd.Series([v[1] for v in values], index=ts).sort_index()
    return series


def longest_negative_run(target):
    neg = target < 0
    gap = target.index.to_series().diff().gt(pd.Timedelta(seconds=20)).fillna(True)
    starts = (neg != neg.shift(fill_value=False)) | gap.to_numpy()
    groups = starts.cumsum()
    runs = target[neg].groupby(groups[neg]).size()
    return int(runs.max()) if len(runs) else 0


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    daily_rows = []
    month_rows = []
    for month in (7, 11):
        sensors = load_selected(month)
        target = sensors["SHAFT_MechPower_kW"]
        raw_daily = target.groupby(target.index.normalize()).agg(
            n_target="size", n_negative=lambda s: int((s < 0).sum()),
            min_kw="min", median_kw="median")
        raw_daily["negative_pct"] = (100 * raw_daily.n_negative / raw_daily.n_target).round(2)
        for day, row in raw_daily.iterrows():
            daily_rows.append({"month": month, "date": day.date().isoformat(),
                               **row.to_dict()})
        minute = pd.concat({
            name: series.resample("1min").mean()
            for name, series in sensors.items()
        }, axis=1)
        negative_minute = minute["SHAFT_MechPower_kW"] < 0
        independent_positive = negative_minute & (minute.ME_RPM_CAMS > 0) & (minute.STW_kn > 3)
        month_rows.append({
            "month": month, "n_target_raw": len(target),
            "n_negative_raw": int((target < 0).sum()),
            "n_days_with_negative": int((raw_daily.n_negative > 0).sum()),
            "min_kw": float(target.min()),
            "longest_near_contiguous_negative_run_readings": longest_negative_run(target),
            "n_negative_1min": int(negative_minute.sum()),
            "n_negative_1min_with_positive_cams_rpm_and_stw_gt_3kn": int(independent_positive.sum()),
            "interpretation": "strong target-quality concern; mechanism and exact calibration boundaries unverified",
        })
        print(month_rows[-1], flush=True)
    pd.DataFrame(daily_rows).to_csv(OUT / "target_quality_daily_jul_nov.csv", index=False)
    pd.DataFrame(month_rows).to_csv(OUT / "target_quality_month_summary.csv", index=False)


if __name__ == "__main__":
    main()
