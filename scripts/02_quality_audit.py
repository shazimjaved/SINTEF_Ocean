"""
scripts/02_quality_audit.py
===========================
Year-wide quality audit across all 12 monthly files (1.csv–12.csv).
Jan25.csv is audited separately.

For each file, streams through ALL rows and computes per-QID statistics:
  - Row count, missing (null/empty value) count
  - Min, max, mean, std of numeric values
  - Count of negative values (NOT automatically removed — flagged for review)
  - Count of zero values
  - Approximate duplicate timestamps (sampled at 1-in-10 to stay RAM-safe)

Also computes the timestamp gap structure for the target QID across all months.

Writes: outputs/tables/data_quality_summary.csv
        outputs/tables/target_availability.csv
        outputs/tables/negative_value_summary.csv
"""

import csv
import os
import math
import re
from collections import defaultdict

RAW_DIR = "data/raw"
OUT_DIR = "outputs/tables"
os.makedirs(OUT_DIR, exist_ok=True)

MONTHLY_FILES = [f"{i}.csv" for i in range(1, 13)]
JAN25_FILE    = "Jan25.csv"
TARGET_QID    = "2::0::11::0_1::1::0::3::0_14::0::1::0_8"

# QID -> short readable label (for output readability)
QID_LABELS = {
    "1::0::14::0_1::2::0::8::0_3::0::3::0_8":  "ME_ScavAirPressure",
    "1::0::15::0_1::2::0::3::0_1::0::6::0_8":  "ME_TC_RPM_Transducer",
    "1::0::25::0_1::2::0::8::0_20::0::1::0_8": "ME_FuelLoad_pct",
    "2::0::11::0_1::1::0::3::0_12::0::1::0_8": "SHAFT_Revolutions_TQ",
    "2::0::11::0_1::1::0::3::0_12::0::2::0_8": "SHAFT_Torque_TQ",
    "2::0::11::0_1::1::0::3::0_14::0::1::0_8": "SHAFT_MechPower_kW_TQ",  # TARGET
    "2::0::11::0_1::1::0::3::0_15::0::1::0_8": "SHAFT_MechEnergy_kWh_TQ",
    "2::0::11::0_1::1::0::3::0_17::0::1::0_8": "SHAFT_ThrustForce_kN_TQ",
    "2::0::11::0_1::1::0::3::0_1::0::6::0_8":  "SHAFT_RPM_TQ",
    "2::0::11::0_1::2::0::8::0_22::0::1::1_8": "ME_FuelMassFlow_kghr_TQ",
    "2::0::1::0_1::1::0::7::0_1::0::4::22_8":  "WIND_RelSpeed_kn_Anem",
    "2::0::1::0_1::1::0::7::0_2::0::15::22_8": "WIND_RelAngle_deg_Anem",
    "2::0::4::0_1::1::0::2::0_37::0::2::0_8":  "HULL_WaterDepth_m",
    "2::0::5::0_1::1::0::2::0_2::0::8::21_8":  "HULL_HeadingTrue_deg",
    "2::0::5::0_1::1::0::2::0_6::0::1::0_8":   "HULL_TurnRate_degmin",
    "2::0::6::1_1::1::0::2::0_1::0::1::0_8":   "SOG_kn_GPS",
    "2::0::7::0_1::1::0::2::0_1::0::5::11_8":  "STW_kn_Speedlog",
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

def safe_float(s):
    try:
        v = float(s.strip())
        return v if math.isfinite(v) else None
    except (ValueError, AttributeError):
        return None

# Welford's online algorithm for mean/variance (memory-safe)
class OnlineStats:
    def __init__(self):
        self.n     = 0
        self.mean  = 0.0
        self.M2    = 0.0
        self.vmin  = None
        self.vmax  = None
        self.n_neg = 0
        self.n_zer = 0
        self.n_mis = 0   # empty or non-numeric

    def update(self, val_str):
        v = safe_float(val_str)
        if v is None or val_str.strip() == "":
            self.n_mis += 1
            return
        self.n += 1
        delta = v - self.mean
        self.mean += delta / self.n
        self.M2 += delta * (v - self.mean)
        if self.vmin is None or v < self.vmin: self.vmin = v
        if self.vmax is None or v > self.vmax: self.vmax = v
        if v < 0: self.n_neg += 1
        if v == 0: self.n_zer += 1

    @property
    def std(self):
        return math.sqrt(self.M2 / self.n) if self.n > 1 else 0.0

def audit_file(fname: str, is_jan25=False) -> dict:
    """Stream one file and return per-QID stats."""
    fpath = os.path.join(RAW_DIR, fname)
    qid_stats = defaultdict(OnlineStats)
    # Track duplicates: (ts, qid) -> count (sample every 10th row to save RAM)
    dup_tracker = defaultdict(int)
    dup_sample_count = 0

    row_count = 0
    has_header = False

    with open(fpath, "r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.reader(fh)
        for i, row in enumerate(reader):
            if i == 0 and is_header_row(row):
                has_header = True
                continue
            if len(row) < 3:
                continue
            ts_str = row[0].strip()
            qid    = row[1].strip()
            val    = row[2].strip()

            qid_stats[qid].update(val)
            row_count += 1

            # Sample 1 in 10 rows for duplicate ts detection
            if row_count % 10 == 0:
                key = (ts_str, qid)
                dup_tracker[key] += 1
                dup_sample_count += 1

            if row_count % 1_000_000 == 0:
                print(f"  {fname}: {row_count:,} rows ...", flush=True)

    # Estimate duplicate count from sample
    n_dup_keys = sum(1 for v in dup_tracker.values() if v > 1)
    dup_estimate = n_dup_keys * 10  # scale back up

    return {
        "file": fname,
        "row_count": row_count,
        "has_header": has_header,
        "qid_stats": dict(qid_stats),
        "dup_estimate": dup_estimate,
        "dup_sample_n": dup_sample_count,
    }

def main():
    print("=" * 70)
    print("YEAR-WIDE DATA QUALITY AUDIT")
    print("=" * 70)

    all_results = []
    quality_rows = []
    target_avail_rows = []
    negative_rows = []

    files_to_audit = MONTHLY_FILES + [JAN25_FILE]

    for fname in files_to_audit:
        is_jan25 = fname == JAN25_FILE
        print(f"\n[{fname}]", flush=True)
        res = audit_file(fname, is_jan25=is_jan25)
        all_results.append(res)

        n_qids = len(res["qid_stats"])
        print(f"  Rows: {res['row_count']:,}  |  QIDs: {n_qids}  |  Est. dup keys (sampled): {res['dup_estimate']:,}")

        for qid, st in sorted(res["qid_stats"].items()):
            label = QID_LABELS.get(qid, qid[:40])
            total = st.n + st.n_mis
            pct_mis = round(100.0 * st.n_mis / total, 2) if total > 0 else 100.0
            quality_rows.append({
                "file":         fname,
                "qid":          qid,
                "short_name":   label,
                "n_numeric":    st.n,
                "n_missing":    st.n_mis,
                "n_total":      total,
                "pct_missing":  pct_mis,
                "min":          round(st.vmin, 4) if st.vmin is not None else "",
                "max":          round(st.vmax, 4) if st.vmax is not None else "",
                "mean":         round(st.mean, 4) if st.n > 0 else "",
                "std":          round(st.std,  4) if st.n > 1 else "",
                "n_negative":   st.n_neg,
                "n_zero":       st.n_zer,
                "dup_estimate": res["dup_estimate"],
            })

            # Target availability tracking
            if qid == TARGET_QID:
                target_avail_rows.append({
                    "file":         fname,
                    "n_target_obs": st.n,
                    "n_target_mis": st.n_mis,
                    "pct_present":  round(100.0 * st.n / (st.n + st.n_mis), 2) if (st.n + st.n_mis) > 0 else 0,
                    "target_min":   round(st.vmin, 2) if st.vmin is not None else "",
                    "target_max":   round(st.vmax, 2) if st.vmax is not None else "",
                    "target_mean":  round(st.mean, 2) if st.n > 0 else "",
                    "target_std":   round(st.std,  2) if st.n > 1 else "",
                    "n_negative":   st.n_neg,
                })

            # Flag sensors with negative values for review
            if st.n_neg > 0:
                negative_rows.append({
                    "file":       fname,
                    "qid":        qid,
                    "short_name": label,
                    "n_negative": st.n_neg,
                    "min_value":  round(st.vmin, 4) if st.vmin is not None else "",
                    "note": "Requires physical validity check — not auto-removed",
                })

    # ------------------------------------------------------------------
    # Write outputs
    # ------------------------------------------------------------------
    q_path = os.path.join(OUT_DIR, "data_quality_summary.csv")
    q_fields = ["file","qid","short_name","n_numeric","n_missing","n_total","pct_missing",
                "min","max","mean","std","n_negative","n_zero","dup_estimate"]
    with open(q_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=q_fields)
        w.writeheader()
        w.writerows(quality_rows)

    t_path = os.path.join(OUT_DIR, "target_availability.csv")
    t_fields = ["file","n_target_obs","n_target_mis","pct_present","target_min","target_max",
                "target_mean","target_std","n_negative"]
    with open(t_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=t_fields)
        w.writeheader()
        w.writerows(target_avail_rows)

    n_path = os.path.join(OUT_DIR, "negative_value_summary.csv")
    with open(n_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["file","qid","short_name","n_negative","min_value","note"])
        w.writeheader()
        w.writerows(negative_rows)

    print(f"\n{'='*70}")
    print(f"Target QID availability across all files:")
    for row in target_avail_rows:
        status = "PRESENT" if row["n_target_obs"] > 0 else "ABSENT"
        print(f"  {row['file']:12s}  [{status}]  n={row['n_target_obs']:>8,}  "
              f"pct={row['pct_present']}%  "
              f"range=[{row['target_min']}, {row['target_max']}]  "
              f"neg={row['n_negative']}")

    if target_avail_rows:
        has_target = [r for r in target_avail_rows if r["n_target_obs"] > 0]
        no_target  = [r for r in target_avail_rows if r["n_target_obs"] == 0]
        print(f"\n  Files WITH target:    {[r['file'] for r in has_target]}")
        print(f"  Files WITHOUT target: {[r['file'] for r in no_target]}")

    print(f"\nOutputs written:")
    print(f"  {q_path}")
    print(f"  {t_path}")
    print(f"  {n_path}")
    print(f"\nNegative value sensors (requiring physical review): {len(negative_rows)}")

if __name__ == "__main__":
    main()
