"""
scripts/05_noon_report_audit.py
================================
Detailed inspection of the 12 Noon Report CSV files.

Produces:
  - Schema verification for each file (columns, types, date format)
  - Missing value counts per column
  - Value range checks (flags anomalous entries for review — not removed)
  - Temporal coverage verification
  - Assessment of join feasibility with minute-resolution sensor data

Writes: outputs/tables/noon_report_quality.csv
"""

import csv
import os
import re
import pandas as pd
import numpy as np

NOON_DIR = "data/Noon Reports"
OUT_DIR  = "outputs/tables"
os.makedirs(OUT_DIR, exist_ok=True)

NOON_FILES = sorted([f for f in os.listdir(NOON_DIR) if f.endswith(".csv")])

def load_noon_report(fname: str) -> pd.DataFrame:
    fpath = os.path.join(NOON_DIR, fname)
    df = pd.read_csv(fpath, encoding="utf-8-sig")
    # Attempt date parsing
    if "Date" in df.columns:
        df["Date_parsed"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    return df

def parse_slip(slip_str) -> float | None:
    """Extract numeric value from Slip strings like '%:  5.86'."""
    if pd.isna(slip_str):
        return None
    m = re.search(r'[-+]?\d+\.?\d*', str(slip_str))
    return float(m.group()) if m else None

def main():
    print("=" * 70)
    print("NOON REPORT DETAILED AUDIT")
    print("=" * 70)

    quality_rows = []
    anomaly_rows = []

    for fname in NOON_FILES:
        print(f"\n[{fname}]")
        df = load_noon_report(fname)

        n_rows = len(df)
        n_cols = len(df.columns)
        print(f"  Shape: {n_rows} rows × {n_cols} columns")
        print(f"  Columns: {list(df.columns)}")

        # Date coverage
        if "Date_parsed" in df.columns:
            d_min = df["Date_parsed"].min()
            d_max = df["Date_parsed"].max()
            n_bad_date = df["Date_parsed"].isna().sum()
            print(f"  Date range: {d_min.date()} .. {d_max.date()}  | bad dates: {n_bad_date}")
        else:
            d_min = d_max = None

        # Per-column stats
        for col in df.columns:
            if col in ("Date", "Date_parsed"):
                continue
            series = df[col]
            n_miss = series.isna().sum()
            pct_miss = round(100.0 * n_miss / n_rows, 1) if n_rows > 0 else 100.0

            # Try numeric
            numeric = pd.to_numeric(series, errors="coerce")
            n_numeric = numeric.notna().sum()
            col_min = col_max = col_mean = ""
            if n_numeric > 0:
                col_min  = round(numeric.min(), 3)
                col_max  = round(numeric.max(), 3)
                col_mean = round(numeric.mean(), 3)

            quality_rows.append({
                "file":        fname,
                "column":      col,
                "n_rows":      n_rows,
                "n_missing":   n_miss,
                "pct_missing": pct_miss,
                "dtype":       str(series.dtype),
                "n_numeric":   n_numeric,
                "min":         col_min,
                "max":         col_max,
                "mean":        col_mean,
                "sample_vals": str(series.dropna().unique()[:3].tolist()),
            })

        # Flag specific anomalies
        # Slip: some entries are wildly large (e.g., -60%, 27%)
        if "Slip" in df.columns:
            slip_vals = df["Slip"].apply(parse_slip)
            extreme = slip_vals[(slip_vals.abs() > 25) | (slip_vals < -20)].dropna()
            if len(extreme) > 0:
                for idx in extreme.index:
                    anomaly_rows.append({
                        "file": fname,
                        "row": idx,
                        "column": "Slip",
                        "raw_value": df.loc[idx, "Slip"],
                        "parsed_value": extreme.loc[idx],
                        "note": "Extreme slip value (>25% or < -20%); requires physical review"
                    })
                print(f"  WARNING: {len(extreme)} extreme Slip values detected")

        # Fuel column: missing in some months
        if "Fuel" in df.columns:
            n_fuel_miss = df["Fuel"].isna().sum()
            print(f"  Fuel column: {n_fuel_miss}/{n_rows} missing")

        # Consumption for Propulsion
        if "Consumption for Propulsion" in df.columns:
            cons = pd.to_numeric(df["Consumption for Propulsion"], errors="coerce")
            n_cons_miss = cons.isna().sum()
            cons_vals = cons.dropna()
            print(f"  Propulsion consumption: {n_cons_miss} missing, "
                  f"range=[{cons_vals.min():.1f}, {cons_vals.max():.1f}] MT/day" if len(cons_vals) > 0
                  else f"  Propulsion consumption: all missing")

    # Write quality table
    q_path = os.path.join(OUT_DIR, "noon_report_quality.csv")
    q_fields = ["file","column","n_rows","n_missing","pct_missing","dtype",
                "n_numeric","min","max","mean","sample_vals"]
    with open(q_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=q_fields)
        w.writeheader()
        w.writerows(quality_rows)

    # Write anomalies
    a_path = os.path.join(OUT_DIR, "noon_report_anomalies.csv")
    a_fields = ["file","row","column","raw_value","parsed_value","note"]
    with open(a_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=a_fields)
        w.writeheader()
        w.writerows(anomaly_rows)

    # Join feasibility assessment
    print("\n" + "="*70)
    print("JOIN FEASIBILITY ASSESSMENT:")
    print("  Noon Reports: daily granularity (one row per calendar day)")
    print("  Sensor data:  sub-minute to hourly depending on sensor")
    print("  Direct join: NOT possible without explicit temporal alignment")
    print("  Proposed use: Noon Report fields (Draft, Displacement, Sea State,")
    print("    Wind Force, Slip) can be used as daily-constant features for the")
    print("    corresponding calendar day in the sensor data — but this approach")
    print("    assumes daily values represent the whole day, which is a strong")
    print("    assumption. Must be documented as a limitation.")
    print("  IMPORTANT: Noon Reports cover Jan 2024–Dec 2024 only. Jan25.csv")
    print("    has no corresponding Noon Report.")

    print(f"\nOutputs written:")
    print(f"  {q_path}")
    print(f"  {a_path}")
    print(f"\nAnomaly entries flagged: {len(anomaly_rows)}")

if __name__ == "__main__":
    main()
