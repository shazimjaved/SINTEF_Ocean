"""
scripts/00_schema_audit.py
==========================
Stream all 13 raw CSVs and the 12 Noon Reports to produce exact row counts,
unique QID sets, confirmed timestamp formats, date coverage per file and
per sensor, and header detection.

Writes: outputs/tables/data_inventory.csv
        outputs/tables/qid_per_file.csv   (QID x file presence matrix)

Memory strategy: line-by-line streaming — no full file is loaded into memory.
Only timestamps are stored in memory for first/last per QID tracking.
"""

import csv
import os
import sys
from collections import defaultdict

RAW_DIR = "data/raw"
NOON_DIR = "data/Noon Reports"
OUT_DIR = "outputs/tables"
os.makedirs(OUT_DIR, exist_ok=True)

RAW_FILES = sorted(
    [f for f in os.listdir(RAW_DIR) if f.endswith(".csv")],
    key=lambda x: (x != "Jan25.csv", x)  # Jan25 last
)

# --------------------------------------------------------------------------
# Helper: detect Jan25 header row (contains F1/F2/F3)
# --------------------------------------------------------------------------
def is_header_row(row: list) -> bool:
    return any(cell.strip().lstrip("\ufeff") in {"F1", "F2", "F3"} for cell in row)

# --------------------------------------------------------------------------
# Stream one raw file
# --------------------------------------------------------------------------
def audit_raw_file(fname: str) -> dict:
    fpath = os.path.join(RAW_DIR, fname)
    size_bytes = os.path.getsize(fpath)

    row_count = 0          # data rows (excluding header)
    has_header = False
    qid_ts_min = {}        # qid -> earliest timestamp string
    qid_ts_max = {}        # qid -> latest  timestamp string  (lexicographic OK for ISO8601)
    qid_row_count = defaultdict(int)
    ts_format_sample = None
    first_data_row = None
    last_data_row = None

    with open(fpath, "r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.reader(fh)
        for i, row in enumerate(reader):
            # Header detection (only possible on row 0)
            if i == 0 and is_header_row(row):
                has_header = True
                continue

            if len(row) < 3:
                # Short/malformed row — skip but count
                continue

            ts_str = row[0].strip()
            qid    = row[1].strip()
            # val  = row[2]  # not needed here

            row_count += 1
            qid_row_count[qid] += 1

            # Track per-QID min/max timestamps (string comparison)
            if qid not in qid_ts_min or ts_str < qid_ts_min[qid]:
                qid_ts_min[qid] = ts_str
            if qid not in qid_ts_max or ts_str > qid_ts_max[qid]:
                qid_ts_max[qid] = ts_str

            if first_data_row is None:
                first_data_row = row
                ts_format_sample = ts_str

            last_data_row = row

            if row_count % 1_000_000 == 0:
                print(f"  {fname}: {row_count:,} rows scanned ...", flush=True)

    # Overall date coverage — min/max across all QIDs
    all_mins = list(qid_ts_min.values())
    all_maxs = list(qid_ts_max.values())
    ts_overall_min = min(all_mins) if all_mins else ""
    ts_overall_max = max(all_maxs) if all_maxs else ""

    return {
        "file": fname,
        "size_mb": round(size_bytes / 1_048_576, 1),
        "has_header": has_header,
        "row_count": row_count,
        "n_unique_qids": len(qid_row_count),
        "ts_format_sample": ts_format_sample,
        "ts_overall_min": ts_overall_min,
        "ts_overall_max": ts_overall_max,
        "qid_row_count": dict(qid_row_count),
        "qid_ts_min": qid_ts_min,
        "qid_ts_max": qid_ts_max,
    }

# --------------------------------------------------------------------------
# Stream Noon Reports (lightweight — they are small)
# --------------------------------------------------------------------------
def audit_noon_reports() -> list:
    results = []
    for fname in sorted(os.listdir(NOON_DIR)):
        if not fname.endswith(".csv"):
            continue
        fpath = os.path.join(NOON_DIR, fname)
        rows = []
        with open(fpath, "r", encoding="utf-8-sig") as fh:
            reader = csv.reader(fh)
            for row in reader:
                rows.append(row)
        header = rows[0] if rows else []
        data_rows = rows[1:] if rows else []
        results.append({
            "file": fname,
            "n_rows": len(data_rows),
            "n_cols": len(header),
            "columns": "|".join(header),
            "date_first": data_rows[0][0] if data_rows else "",
            "date_last":  data_rows[-1][0] if data_rows else "",
        })
    return results

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("SCHEMA AUDIT: Streaming all 13 raw CSVs")
    print("=" * 70)

    raw_results = []
    all_qids = set()
    file_qid_matrix = {}   # fname -> set of qids

    for fname in RAW_FILES:
        print(f"\n[{fname}]", flush=True)
        result = audit_raw_file(fname)
        raw_results.append(result)
        qids = set(result["qid_row_count"].keys())
        all_qids.update(qids)
        file_qid_matrix[fname] = qids
        print(
            f"  Rows: {result['row_count']:,}  |  Unique QIDs: {result['n_unique_qids']}  |  "
            f"Header: {result['has_header']}  |  "
            f"TS range: {result['ts_overall_min']}  ..  {result['ts_overall_max']}"
        )

    # ------------------------------------------------------------------
    # Write data_inventory.csv
    # ------------------------------------------------------------------
    inv_path = os.path.join(OUT_DIR, "data_inventory.csv")
    inv_fields = [
        "file", "size_mb", "has_header", "row_count", "n_unique_qids",
        "ts_format_sample", "ts_overall_min", "ts_overall_max"
    ]
    with open(inv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=inv_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(raw_results)

    # Compute verified totals
    total_12 = sum(r["row_count"] for r in raw_results if r["file"] != "Jan25.csv")
    total_all = sum(r["row_count"] for r in raw_results)
    print(f"\n{'='*70}")
    print(f"Verified total rows (1.csv–12.csv):     {total_12:,}")
    print(f"Verified total rows (all 13 files):     {total_all:,}")
    print(f"Total unique QIDs across all files:     {len(all_qids)}")

    # ------------------------------------------------------------------
    # Write qid_per_file.csv  (QID x file presence matrix)
    # ------------------------------------------------------------------
    qid_fields = ["qid"] + RAW_FILES
    qp_path = os.path.join(OUT_DIR, "qid_per_file.csv")
    with open(qp_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(qid_fields)
        for qid in sorted(all_qids):
            row = [qid] + ["1" if qid in file_qid_matrix[f] else "0" for f in RAW_FILES]
            w.writerow(row)

    # ------------------------------------------------------------------
    # Per-QID row counts per file  (detailed)
    # ------------------------------------------------------------------
    print("\n\nQID presence per file:")
    for fname in RAW_FILES:
        print(f"\n  {fname} — QIDs observed ({len(file_qid_matrix[fname])}):")
        for qid in sorted(file_qid_matrix[fname]):
            cnt = raw_results[RAW_FILES.index(fname)]["qid_row_count"][qid]
            ts_min = raw_results[RAW_FILES.index(fname)]["qid_ts_min"][qid]
            ts_max = raw_results[RAW_FILES.index(fname)]["qid_ts_max"][qid]
            print(f"    {qid}  rows={cnt:>9,}  ts=[{ts_min} .. {ts_max}]")

    # ------------------------------------------------------------------
    # Noon Reports
    # ------------------------------------------------------------------
    print("\n\nNOON REPORTS:")
    noon_results = audit_noon_reports()
    for nr in noon_results:
        print(f"  {nr['file']}: {nr['n_rows']} data rows, {nr['n_cols']} cols")
        print(f"    Columns: {nr['columns']}")
        print(f"    Date range: {nr['date_first']} .. {nr['date_last']}")

    noon_path = os.path.join(OUT_DIR, "noon_report_inventory.csv")
    noon_fields = ["file","n_rows","n_cols","columns","date_first","date_last"]
    with open(noon_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=noon_fields)
        w.writeheader()
        w.writerows(noon_results)

    print(f"\n\nOutputs written:")
    print(f"  {inv_path}")
    print(f"  {qp_path}")
    print(f"  {noon_path}")

if __name__ == "__main__":
    main()
