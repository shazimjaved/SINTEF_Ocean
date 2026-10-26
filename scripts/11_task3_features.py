"""Stream 2024 long-form CSVs into completed-minute Task 3 feature tables.

The interval labelled t is [t-1 minute, t). No observation at/after t enters
onboard averages. External observations are last-known by raw timestamp before
t and at most 60 minutes old; provider issue-time semantics remain unknown.
Run from the project root. Each month is processed independently in 200k chunks.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from channel_config import ANGLE_COLUMNS, CHANNELS, MODEL_CANDIDATES, TARGET

RAW = Path("data/raw")
OUT = Path("outputs/task3/data")
TABLES = Path("outputs/task3/tables")
MINUTE_NS = 60_000_000_000
QIDS = list(CHANNELS)
COLS = [CHANNELS[q][0] for q in QIDS]
SOURCES = [CHANNELS[q][1] for q in QIDS]
COLUMN_SOURCE = {col: source for col, source in zip(COLS, SOURCES)}
ENV_IDX = [i for i, s in enumerate(SOURCES) if s.startswith("provider_")]
ANGLE_IDX = [i for i, c in enumerate(COLS) if c in ANGLE_COLUMNS]
TARGET_IDX = COLS.index(TARGET)
QID_INDEX = {q: i for i, q in enumerate(QIDS)}


def month_frame(month: int, carry: dict) -> tuple[pd.DataFrame, dict, dict]:
    start = pd.Timestamp(2024, month, 1, tz="UTC")
    stop = start + pd.offsets.MonthBegin(1)
    n = int((stop.value - start.value) // MINUTE_NS)
    sums = np.zeros((len(QIDS), n), dtype=np.float64)
    counts = np.zeros((len(QIDS), n), dtype=np.int32)
    sins = {i: np.zeros(n, dtype=np.float64) for i in ANGLE_IDX}
    coss = {i: np.zeros(n, dtype=np.float64) for i in ANGLE_IDX}
    env_ns = {i: np.full(n, -1, dtype=np.int64) for i in ENV_IDX}
    env_val = {i: np.full(n, np.nan, dtype=np.float64) for i in ENV_IDX}
    target_neg = np.zeros(n, dtype=np.int16)
    target_min = np.full(n, np.inf)
    rows = 0
    path = RAW / f"{month}.csv"
    reader = pd.read_csv(path, header=None, names=["ts", "qid", "value"],
                         dtype={"ts": "string", "qid": "string", "value": "float64"},
                         chunksize=200_000)
    for chunk in reader:
        rows += len(chunk)
        qi = chunk.qid.map(QID_INDEX).to_numpy()
        if pd.isna(qi).any():
            raise ValueError(f"Unknown QID in {path}: {chunk.qid[pd.isna(qi)].iloc[0]}")
        qi = qi.astype(np.int16)
        values = chunk.value.to_numpy(dtype=np.float64)
        if not np.isfinite(values).all():
            raise ValueError(f"Nonfinite sensor value in {path}")
        ts_ns = pd.DatetimeIndex(pd.to_datetime(chunk.ts, utc=True, errors="raise")).as_unit("ns").asi8
        mi = ((ts_ns - start.value) // MINUTE_NS).astype(np.int32)
        if np.any((mi < 0) | (mi >= n)):
            raise ValueError(f"Timestamp outside named month in {path}")
        np.add.at(sums, (qi, mi), values)
        np.add.at(counts, (qi, mi), 1)
        for i in ANGLE_IDX:
            use = qi == i
            if use.any():
                radians = np.deg2rad(values[use])
                np.add.at(sins[i], mi[use], np.sin(radians))
                np.add.at(coss[i], mi[use], np.cos(radians))
        target_use = qi == TARGET_IDX
        if target_use.any():
            np.add.at(target_neg, mi[target_use & (values < 0)], 1)
            np.minimum.at(target_min, mi[target_use], values[target_use])
        for i in ENV_IDX:
            use = np.flatnonzero(qi == i)
            # Provider data are sparse. Keep the latest exact raw timestamp in
            # each minute, including when file rows are not time sorted.
            for k in use:
                minute = mi[k]
                if ts_ns[k] > env_ns[i][minute]:
                    env_ns[i][minute] = ts_ns[k]
                    env_val[i][minute] = values[k]

    end_ns = start.value + (np.arange(n, dtype=np.int64) + 1) * MINUTE_NS
    result = {"window_end_utc": pd.to_datetime(end_ns, utc=True).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "source_month": np.full(n, month, dtype=np.uint8)}
    new_carry = {}
    for i, col in enumerate(COLS):
        if i in ENV_IDX:
            # Carry only the latest raw provider value from prior month.
            previous_ns, previous_val = carry.get(i, (-1, np.nan))
            observed = env_ns[i] >= 0
            last_ns = np.maximum(np.maximum.accumulate(env_ns[i]), previous_ns)
            last_val = pd.Series(np.where(observed, env_val[i], np.nan)).ffill().fillna(previous_val).to_numpy(dtype=np.float64)
            age_s = (end_ns - last_ns) / 1e9
            fresh = (last_ns >= 0) & (age_s >= 0) & (age_s <= 3600)
            result[col] = np.where(fresh, last_val, np.nan).astype(np.float32)
            result[f"age_s__{col}"] = np.where(fresh, age_s, np.nan).astype(np.float32)
            if observed.any():
                k = np.flatnonzero(observed)[-1]
                new_carry[i] = (int(env_ns[i][k]), float(env_val[i][k]))
            else:
                new_carry[i] = (int(previous_ns), float(previous_val))
        else:
            result[col] = np.divide(sums[i], counts[i], out=np.full(n, np.nan), where=counts[i] > 0).astype(np.float32)
            if col in MODEL_CANDIDATES:
                result[f"n__{col}"] = counts[i].astype(np.uint16)
        if i in ANGLE_IDX:
            if i in ENV_IDX:
                radians = np.deg2rad(result[col].astype(np.float64))
                result[f"sin__{col}"] = np.sin(radians).astype(np.float32)
                result[f"cos__{col}"] = np.cos(radians).astype(np.float32)
            else:
                direction = np.arctan2(sins[i], coss[i])
                valid = counts[i] > 0
                result[col] = np.where(valid, np.rad2deg(direction) % 360, np.nan).astype(np.float32)
                result[f"sin__{col}"] = np.where(valid, np.sin(direction), np.nan).astype(np.float32)
                result[f"cos__{col}"] = np.where(valid, np.cos(direction), np.nan).astype(np.float32)
                result[f"resultant__{col}"] = np.divide(np.hypot(sins[i], coss[i]), counts[i],
                    out=np.full(n, np.nan), where=valid).astype(np.float32)
    result["target_n"] = counts[TARGET_IDX].astype(np.uint16)
    result["target_negative_n"] = target_neg
    result["target_min"] = np.where(counts[TARGET_IDX] > 0, target_min, np.nan).astype(np.float32)
    # Export only approved predictors and the target/label-quality columns.
    # No torquemeter proxy, draft or depth column enters the reusable table.
    keep = {"window_end_utc", "source_month", TARGET, "target_n",
            "target_negative_n", "target_min"}
    for col in MODEL_CANDIDATES:
        keep.add(col)
        if col in ANGLE_COLUMNS:
            keep.update({f"sin__{col}", f"cos__{col}"})
            if COLUMN_SOURCE[col] == "onboard":
                keep.add(f"resultant__{col}")
        if COLUMN_SOURCE[col] == "onboard":
            keep.add(f"n__{col}")
        else:
            keep.add(f"age_s__{col}")
    frame = pd.DataFrame({key: value for key, value in result.items() if key in keep})
    summary = {"month": month, "raw_rows": rows, "completed_minutes": n,
               "target_minutes": int((counts[TARGET_IDX] > 0).sum()),
               "negative_target_minutes": int((target_neg > 0).sum()),
               "candidate_features": len(MODEL_CANDIDATES)}
    return frame, new_carry, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", nargs="+", type=int, default=list(range(1, 13)))
    args = parser.parse_args()
    months = args.months
    if months != list(range(months[0], months[-1] + 1)):
        raise ValueError("Months must be consecutive for provider carry-forward")
    OUT.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    carry = {}
    summaries = []
    for month in months:
        t0 = time.perf_counter()
        frame, carry, summary = month_frame(month, carry)
        destination = OUT / f"minute_2024_{month:02d}.csv.gz"
        frame.to_csv(destination, index=False, compression="gzip", float_format="%.6g")
        summary["elapsed_s"] = round(time.perf_counter() - t0, 1)
        summary["output_bytes"] = destination.stat().st_size
        summaries.append(summary)
        print(summary, flush=True)
    pd.DataFrame(summaries).to_csv(TABLES / "feature_build_summary.csv", index=False)
    manifest = {"window": "[end-1 minute, end)", "timezone": "UTC for 2024 Z timestamps",
                "provider_rule": "latest raw timestamp before end, maximum age 3600s; issue time unknown",
                "columns": {col: {"qid": q, "source": source} for q, (col, source) in CHANNELS.items()},
                "candidate_columns": sorted(MODEL_CANDIDATES),
                "excluded_from_model": sorted(set(COLS) - MODEL_CANDIDATES)}
    (TABLES / "feature_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
