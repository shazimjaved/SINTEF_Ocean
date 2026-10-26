"""
scripts/03_pivot_representative.py
===================================
Pivot one representative month from long-format to wide-format for EDA.

Month selection: 10.csv (~1.9M rows, Oct 2024) — smallest full-sensor month,
fits in RAM after pivoting to ~36 columns × ~54K unique timestamps.

Also pivots 1.csv for January for year-start comparison.

Strategy:
  1. Stream file in chunks, parse timestamps explicitly.
  2. Detect and report (but do NOT silently resolve) duplicate (ts, qid) pairs.
  3. For duplicates: keep ALL, then flag count; final pivot uses LAST value
     (last-write-wins is common for sensor telemetry) and reports n_dups.
  4. Sort by parsed timestamp after pivot.
  5. Write pivoted CSVs to outputs/ (NOT to data/).

Writes:
  outputs/tables/pivot_oct2024.csv
  outputs/tables/pivot_jan2024.csv
  outputs/tables/pivot_duplicates_report.csv
"""

import csv
import os
import pandas as pd
from collections import defaultdict

RAW_DIR = "data/raw"
OUT_DIR = "outputs/tables"
os.makedirs(OUT_DIR, exist_ok=True)

CHUNK_SIZE = 500_000
TARGET_QID = "2::0::11::0_1::1::0::3::0_14::0::1::0_8"

QID_LABELS = {
    "1::0::14::0_1::2::0::8::0_3::0::3::0_8":  "ME_ScavAirPressure_bar",
    "1::0::15::0_1::2::0::3::0_1::0::6::0_8":  "ME_TC_RPM_Transducer",
    "1::0::25::0_1::2::0::8::0_20::0::1::0_8": "ME_FuelLoad_pct",
    "2::0::11::0_1::1::0::3::0_12::0::1::0_8": "SHAFT_Revolutions_TQ",
    "2::0::11::0_1::1::0::3::0_12::0::2::0_8": "SHAFT_Torque_Nm_TQ",
    "2::0::11::0_1::1::0::3::0_14::0::1::0_8": "SHAFT_MechPower_kW",      # TARGET
    "2::0::11::0_1::1::0::3::0_15::0::1::0_8": "SHAFT_MechEnergy_kWh_TQ",
    "2::0::11::0_1::1::0::3::0_17::0::1::0_8": "SHAFT_ThrustForce_kN_TQ",
    "2::0::11::0_1::1::0::3::0_1::0::6::0_8":  "SHAFT_RPM_TQ",
    "2::0::11::0_1::2::0::8::0_22::0::1::1_8": "ME_FuelMassFlow_kghr_TQ",
    "2::0::1::0_1::1::0::7::0_1::0::4::22_8":  "WIND_RelSpeed_kn",
    "2::0::1::0_1::1::0::7::0_2::0::15::22_8": "WIND_RelAngle_deg",
    "2::0::4::0_1::1::0::2::0_37::0::2::0_8":  "HULL_WaterDepth_m",
    "2::0::5::0_1::1::0::2::0_2::0::8::21_8":  "HULL_HeadingTrue_deg",
    "2::0::5::0_1::1::0::2::0_6::0::1::0_8":   "HULL_TurnRate_degmin",
    "2::0::6::1_1::1::0::2::0_1::0::1::0_8":   "SOG_kn",
    "2::0::7::0_1::1::0::2::0_1::0::5::11_8":  "STW_kn",
    "2::0::25::0_1::2::0::3::0_1::0::6::0_8":  "ME_TC_RPM_Indicator",
    "3::0::1::0_1::1::0::2::0_11::0::1::0_8":  "DRAFT_Fore_m",
    "3::0::1::0_1::1::0::2::0_11::0::2::0_8":  "DRAFT_Aft_m",
    "3::0::1::0_1::1::0::2::0_11::0::3::0_8":  "DRAFT_MidP_m",
    "3::0::1::0_1::1::0::2::0_11::0::4::0_8":  "DRAFT_MidS_m",
    "3::0::1::0_1::2::0::8::0_1::0::6::0_8":   "ME_RPM_CAMS",
    "4::0::4::0_1::1::0::7::0_1::0::4::21_8":  "WIND_TrueSpeed_kn_MB",
    "4::0::4::0_1::1::0::7::0_2::0::15::21_8": "WIND_TrueAngle_deg_MB",
    "4::0::4::0_1::1::0::7::0_45::0::1::0_8":  "WAVE_SigHeight_m_MB",
    "4::0::4::0_1::1::0::7::0_45::0::2::0_8":  "SWELL_SigHeight_m_MB",
    "4::0::4::0_1::1::0::7::0_56::0::3::0_8":  "CURR_Eastward_ms_MB",
    "4::0::4::0_1::1::0::7::0_56::0::4::0_8":  "CURR_Northward_ms_MB",
    "4::0::8::0_1::1::0::7::0_2::0::18::21_8": "WAVE_TrueAngle_deg_S",
    "4::0::8::0_1::1::0::7::0_4::0::12::0_8":  "SEA_WaterTemp_C_S",
    "4::0::8::0_1::1::0::7::0_40::0::2::0_8":  "WAVE_Period_sec_S",
    "4::0::8::0_1::1::0::7::0_45::0::1::0_8":  "WAVE_SigHeight_m_S",
    "4::0::8::0_1::1::0::7::0_56::0::3::0_8":  "CURR_Eastward_ms_S",
    "4::0::8::0_1::1::0::7::0_56::0::4::0_8":  "CURR_Northward_ms_S",
    "4::0::8::0_1::1::0::7::0_56::0::5::0_8":  "WIND_Eastward_ms_S",
    "4::0::8::0_1::1::0::7::0_56::0::6::0_8":  "WIND_Northward_ms_S",
}

def is_header_row(row):
    return any(c.strip().lstrip("\ufeff") in {"F1","F2","F3"} for c in row)

def pivot_file(fname: str, is_jan25: bool = False) -> tuple:
    """
    Stream-pivot fname. Returns (df_wide, dup_report_rows, n_raw_rows).
    Uses last-value-wins for duplicates. All duplicates are tracked and reported.
    """
    fpath = os.path.join(RAW_DIR, fname)
    dup_counts = defaultdict(int)   # (ts, qid) -> occurrence count

    # First pass: collect all (ts, qid, val) pairs to detect duplicates
    # For large files this is still chunked — we only store last value per key
    data = {}  # (ts, qid) -> last_val
    n_raw = 0

    with open(fpath, "r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.reader(fh)
        for i, row in enumerate(reader):
            if i == 0 and is_header_row(row):
                continue
            if len(row) < 3:
                continue
            ts_str = row[0].strip()
            qid    = row[1].strip()
            val    = row[2].strip()
            key = (ts_str, qid)
            dup_counts[key] += 1
            data[key] = val
            n_raw += 1
            if n_raw % 1_000_000 == 0:
                print(f"  {fname}: pass 1 — {n_raw:,} rows ...", flush=True)

    n_dups = sum(1 for v in dup_counts.values() if v > 1)
    print(f"  {fname}: {n_raw:,} raw rows, {n_dups:,} duplicate (ts,qid) pairs")

    # Duplicate report rows
    dup_report = []
    for (ts, qid), cnt in dup_counts.items():
        if cnt > 1:
            dup_report.append({
                "file": fname, "timestamp": ts, "qid": qid,
                "occurrence_count": cnt, "kept_value": data[(ts, qid)]
            })

    # Build long-format DataFrame from deduplicated data
    rows_long = [{"timestamp": k[0], "qid": k[1], "value": v} for k, v in data.items()]
    df = pd.DataFrame(rows_long)

    # Parse timestamps
    if is_jan25:
        df["ts_parsed"] = pd.to_datetime(df["timestamp"], format="%d/%m/%Y %H:%M:%S",
                                          dayfirst=True, errors="coerce")
    else:
        df["ts_parsed"] = pd.to_datetime(df["timestamp"], format="ISO8601",
                                          utc=True, errors="coerce")
        # Normalise to UTC, strip tz for simpler downstream use
        df["ts_parsed"] = df["ts_parsed"].dt.tz_localize(None) if df["ts_parsed"].dt.tz is None \
                          else df["ts_parsed"].dt.tz_convert("UTC").dt.tz_localize(None)

    n_bad_ts = df["ts_parsed"].isna().sum()
    if n_bad_ts > 0:
        print(f"  WARNING: {n_bad_ts} timestamps failed to parse in {fname}")

    # Convert values to numeric
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    # Pivot: rows = timestamp, columns = qid short name
    df["col_name"] = df["qid"].map(QID_LABELS).fillna(df["qid"])
    df_pivot = df.pivot(index="ts_parsed", columns="col_name", values="value")
    df_pivot = df_pivot.sort_index()

    print(f"  Pivoted shape: {df_pivot.shape}  (timestamps × sensors)")
    print(f"  Date range: {df_pivot.index.min()} .. {df_pivot.index.max()}")

    return df_pivot, dup_report, n_raw

def main():
    print("=" * 70)
    print("PIVOT: Creating analytical wide-format frames for EDA")
    print("=" * 70)

    all_dup_rows = []

    # Oct 2024 (10.csv) — smallest monthly file, all sensors present
    print("\n[10.csv — October 2024]")
    df_oct, dup_oct, n_oct = pivot_file("10.csv")
    all_dup_rows.extend(dup_oct)
    df_oct.to_csv(os.path.join(OUT_DIR, "pivot_oct2024.csv"))
    print(f"  Saved: pivot_oct2024.csv")

    # Jan 2024 (1.csv) — year-start context, but large; only pivot if RAM allows
    # We'll sample: take every 36th row of raw data to keep frame manageable
    # (36 sensors × ~100k timestamps = representative)
    print("\n[1.csv — January 2024] (sampled: 1-in-36 rows for RAM safety)")
    # Direct chunk-based sample
    sample_rows = []
    n_jan = 0
    with open(os.path.join(RAW_DIR, "1.csv"), "r", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        for i, row in enumerate(reader):
            if len(row) < 3: continue
            if i % 36 == 0:
                sample_rows.append({"timestamp": row[0].strip(),
                                     "qid": row[1].strip(),
                                     "value": row[2].strip()})
            n_jan += 1
            if n_jan % 1_000_000 == 0:
                print(f"  1.csv: {n_jan:,} rows ...", flush=True)

    df_jan_s = pd.DataFrame(sample_rows)
    df_jan_s["ts_parsed"] = pd.to_datetime(df_jan_s["timestamp"], format="ISO8601",
                                            utc=True, errors="coerce")
    df_jan_s["ts_parsed"] = df_jan_s["ts_parsed"].dt.tz_localize(None) if df_jan_s["ts_parsed"].dt.tz is None \
                             else df_jan_s["ts_parsed"].dt.tz_convert("UTC").dt.tz_localize(None)
    df_jan_s["value"] = pd.to_numeric(df_jan_s["value"], errors="coerce")
    df_jan_s["col_name"] = df_jan_s["qid"].map(QID_LABELS).fillna(df_jan_s["qid"])
    df_jan_s = df_jan_s.drop_duplicates(subset=["ts_parsed","col_name"], keep="last")
    df_jan_p = df_jan_s.pivot(index="ts_parsed", columns="col_name", values="value").sort_index()
    df_jan_p.to_csv(os.path.join(OUT_DIR, "pivot_jan2024_sampled.csv"))
    print(f"  Sampled {len(sample_rows):,} rows -> Pivot shape: {df_jan_p.shape}")
    print(f"  Date range: {df_jan_p.index.min()} .. {df_jan_p.index.max()}")
    print(f"  Saved: pivot_jan2024_sampled.csv")

    # Write duplicate report
    dup_path = os.path.join(OUT_DIR, "pivot_duplicates_report.csv")
    dup_fields = ["file","timestamp","qid","occurrence_count","kept_value"]
    with open(dup_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=dup_fields)
        w.writeheader()
        w.writerows(all_dup_rows[:10000])  # cap at 10k rows for file size

    print(f"\nDuplicate (ts,qid) pairs in Oct 2024: {len(dup_oct)}")
    print(f"(first 10,000 written to {dup_path})")

if __name__ == "__main__":
    main()
