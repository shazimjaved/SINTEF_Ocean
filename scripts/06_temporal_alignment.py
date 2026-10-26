"""October descriptive alignment and coverage audit.

Rows are labelled by the END of a trailing one-minute interval (start, end].
Thus the onboard average contains no observation after its label. These rows
describe a completed minute; they are not instantaneous measurements at its
start and are not yet a model-ready point-in-time feature table.

External values use the latest raw timestamp at or before the interval end,
with an exact maximum age of 60 minutes. Whether a provider timestamp denotes
issue time or weather-valid time is not established by this dataset.
"""

from pathlib import Path
import numpy as np
import pandas as pd
from channel_config import (
    ANGLE_COLUMNS, COLUMN_TO_SOURCE, DRAFT, ENVIRONMENTAL, LEAKAGE,
    MODEL_CANDIDATES, ONBOARD, TARGET,
)

TABLES = Path("outputs/tables")
PIVOT = TABLES / "pivot_oct2024.csv"
START = pd.Timestamp("2024-10-01 00:01:00")
END = pd.Timestamp("2024-11-01 00:00:00")
GRID = pd.date_range(START, END, freq="1min")
TOLERANCE = pd.Timedelta(minutes=60)


def load_pivot():
    frame = pd.read_csv(PIVOT, index_col=0, parse_dates=True)
    frame = frame.sort_index()
    observed = set(frame.columns)
    expected = set(COLUMN_TO_SOURCE)
    if observed != expected:
        raise ValueError(f"Pivot/config mismatch: unknown={observed - expected}, missing={expected - observed}")
    if frame.index.has_duplicates:
        raise ValueError("Pivot has duplicate timestamps; resolve before alignment")
    return frame


def align(frame):
    # pandas' left-labelled [t,t+1min) bin is shifted to its completion time.
    onboard = frame[sorted(ONBOARD)].resample("1min").mean()
    onboard.index = onboard.index + pd.Timedelta(minutes=1)
    onboard = onboard.reindex(GRID)
    env = {}
    provenance = {}
    for col in sorted(ENVIRONMENTAL):
        raw = frame[col].dropna()
        env[col] = raw.reindex(GRID, method="ffill", tolerance=TOLERANCE)
        # Retain the exact raw observation index used by each filled value.
        loc = raw.index.searchsorted(GRID, side="right") - 1
        valid = loc >= 0
        source = np.full(len(GRID), -1, dtype=np.int32)
        candidate = np.flatnonzero(valid)
        age = GRID.asi8[candidate] - raw.index.asi8[loc[candidate]]
        source[candidate[age <= TOLERANCE.value]] = loc[candidate[age <= TOLERANCE.value]]
        provenance[col] = source
    aligned = pd.concat([onboard, pd.DataFrame(env, index=GRID)], axis=1)
    return aligned, provenance


def write_tables(raw, aligned, provenance):
    TABLES.mkdir(parents=True, exist_ok=True)
    target_present = aligned[TARGET].notna()
    n_target = int(target_present.sum())

    summary = []
    overlap = []
    for col in sorted(raw.columns):
        present = aligned[col].notna()
        source = COLUMN_TO_SOURCE[col]
        if col == TARGET:
            role = "target"
        elif col in LEAKAGE:
            role = "excluded_torquemeter"
        elif col in DRAFT:
            role = "excluded_constant_zero_draft"
        elif col == "HULL_WaterDepth_m":
            role = "excluded_no_october_overlap"
        else:
            role = "candidate"
        n_pair = int((target_present & present).sum())
        distinct_raw = ""
        if col in provenance:
            used = provenance[col][(target_present & present).to_numpy()]
            distinct_raw = int(np.unique(used[used >= 0]).size)
        summary.append({
            "sensor": col, "source_group": source, "feature_role": role,
            "n_raw_october": int(raw[col].notna().sum()),
            "n_expected_completed_minutes": len(GRID),
            "n_present_after_alignment": int(present.sum()),
            "pct_coverage_aligned": round(100 * present.mean(), 2),
            "timestamp_semantics": "trailing_minute_end" if col in ONBOARD else "latest_raw_timestamp_age_le_60min",
        })
        if col != TARGET:
            overlap.append({
                "predictor": col, "source_group": source, "feature_role": role,
                "n_target_completed_minutes": n_target,
                "n_predictor_completed_minutes": int(present.sum()),
                "n_coobserved_completed_minutes": n_pair,
                "pct_target_with_predictor": round(100 * n_pair / n_target, 2),
                "n_distinct_raw_provider_timestamps_used": distinct_raw,
            })
    pd.DataFrame(summary).to_csv(TABLES / "alignment_summary.csv", index=False)
    pd.DataFrame(overlap).to_csv(TABLES / "overlap_stats_oct2024.csv", index=False)

    daily = raw.notna().groupby(raw.index.normalize()).sum()
    daily = daily.reindex(pd.date_range("2024-10-01", "2024-10-31", freq="D"), fill_value=0)
    daily.to_csv(TABLES / "coverage_per_qid_oct2024.csv")

    # This is monthly target-count density, not a year-wide feature-overlap test.
    target_monthly = pd.read_csv(TABLES / "target_availability.csv").set_index("file")
    monthly = []
    for month in range(1, 13):
        row = target_monthly.loc[f"{month}.csv"]
        days = pd.Period(f"2024-{month:02d}").days_in_month
        expected = days * 24 * 60 * 4
        monthly.append({
            "month": pd.Timestamp(2024, month, 1).strftime("%b"), "file": f"{month}.csv",
            "days_in_month": days, "expected_at_nominal_15sec": expected,
            "n_target_obs": int(row.n_target_obs),
            "pct_of_nominal_15sec": round(100 * row.n_target_obs / expected, 1),
            "n_negative": int(row.n_negative), "target_min": float(row.target_min),
            "target_max": float(row.target_max),
            "interpretation": "observation-count density, not uptime or missing-value rate",
        })
    pd.DataFrame(monthly).to_csv(TABLES / "overlap_stats_yearwide.csv", index=False)

    # Pearson is restricted to numeric scalar channels. Angular variables need
    # circular or vector treatment; constant-zero draft and sparse depth are out.
    corr_cols = [TARGET] + sorted(MODEL_CANDIDATES - ANGLE_COLUMNS)
    values = aligned[corr_cols]
    paired = values.notna().astype(np.int32).T.dot(values.notna().astype(np.int32))
    corr = values.corr(min_periods=30)
    corr.to_csv(TABLES / "correlation_aligned.csv")
    paired.to_csv(TABLES / "correlation_paired_n.csv")
    overlap_by_name = {row["predictor"]: row for row in overlap}
    evidence = []
    for col in corr_cols[1:]:
        ov = overlap_by_name[col]
        evidence.append({
            "predictor": col, "source_group": COLUMN_TO_SOURCE[col],
            "pearson_r_october": corr.loc[TARGET, col],
            "n_paired_completed_minutes": int(paired.loc[TARGET, col]),
            "n_distinct_raw_provider_timestamps_used": ov["n_distinct_raw_provider_timestamps_used"],
            "caution": "descriptive; paired minutes are autocorrelated and weather values repeat",
        })
    pd.DataFrame(evidence).to_csv(TABLES / "correlation_target_evidence.csv", index=False)
    print(f"October: {n_target:,} target completed minutes; {len(ENVIRONMENTAL)} external channels; "
          f"{len(MODEL_CANDIDATES)} candidate channels.")
    print("Tables: alignment_summary, coverage_per_qid_oct2024, overlap_stats_oct2024, "
          "overlap_stats_yearwide, correlation_aligned, correlation_paired_n, correlation_target_evidence")


if __name__ == "__main__":
    raw = load_pivot()
    aligned, provenance = align(raw)
    write_tables(raw, aligned, provenance)
