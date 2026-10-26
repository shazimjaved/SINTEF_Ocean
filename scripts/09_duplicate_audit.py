"""Exact year-wide (timestamp, QID) duplicate audit, one raw file at a time.

The compact in-memory keys contain the original timestamp bytes plus one QID
code. Each file's set is discarded before reading the next file. This avoids
loading a monthly DataFrame or maintaining a year-wide key set.
"""

import csv
from pathlib import Path
import pandas as pd
from channel_config import CHANNELS

RAW = Path("data/raw")
OUT = Path("outputs/tables/duplicate_audit_yearwide.csv")
QID_CODE = {qid: i for i, qid in enumerate(CHANNELS)}
assert len(QID_CODE) < 256


def key_of(row):
    try:
        return row[0].encode("utf-8") + b"\x1f" + bytes((QID_CODE[row[1]],))
    except KeyError as exc:
        raise ValueError(f"Unknown QID in duplicate audit: {exc}") from exc


def audit_file(path):
    keys = set()
    duplicate_keys = set()
    physical_rows = 0
    malformed = 0
    extra_rows = 0
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.reader(fh):
            if row and row[0] == "F1":
                continue
            physical_rows += 1
            if len(row) < 3:
                malformed += 1
                continue
            key = key_of(row)
            if key in keys:
                extra_rows += 1
                duplicate_keys.add(key)
            else:
                keys.add(key)
    unique_pairs = len(keys)
    del keys
    conflicting_keys = 0
    if duplicate_keys:
        first_value = {}
        conflicts = set()
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.reader(fh):
                if len(row) < 3 or (row and row[0] == "F1"):
                    continue
                key = key_of(row)
                if key not in duplicate_keys:
                    continue
                if key in first_value and row[2] != first_value[key]:
                    conflicts.add(key)
                else:
                    first_value.setdefault(key, row[2])
        conflicting_keys = len(conflicts)
    return {
        "file": path.name, "physical_rows": physical_rows,
        "unique_timestamp_qid_pairs": unique_pairs,
        "duplicate_keys": len(duplicate_keys), "extra_duplicate_rows": extra_rows,
        "conflicting_value_keys": conflicting_keys, "malformed_short_rows": malformed,
        "method": "exact original timestamp text + exact registered QID; per-file set",
    }


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in [f"{i}.csv" for i in range(1, 13)] + ["Jan25.csv"]:
        result = audit_file(RAW / name)
        rows.append(result)
        print(name, "rows", result["physical_rows"], "duplicate keys",
              result["duplicate_keys"], "extra rows", result["extra_duplicate_rows"], flush=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print("Total duplicate keys:", sum(r["duplicate_keys"] for r in rows))


if __name__ == "__main__":
    main()
