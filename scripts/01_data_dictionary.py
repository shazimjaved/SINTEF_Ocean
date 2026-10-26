"""
scripts/01_data_dictionary.py
=============================
Parse the Metrics Registration PDF to extract all registered QID mappings,
then reconcile against QIDs actually observed in raw CSVs.

Produces a complete, explicit mapping reconciliation table.

Writes: outputs/tables/data_dictionary.csv
        outputs/tables/qid_reconciliation.csv

Also classifies each QID for leakage risk and feature group.
"""

import csv
import os
import re
import fitz  # PyMuPDF
from channel_config import CHANNELS, DRAFT, LEAKAGE, MODEL_CANDIDATES, TARGET as TARGET_COLUMN

PDF_PATH = "docs/Metrics registration - Google Sheets.pdf"
QID_PER_FILE = "outputs/tables/qid_per_file.csv"
QUALITY_SUMMARY = "outputs/tables/data_quality_summary.csv"
DATA_INVENTORY = "outputs/tables/data_inventory.csv"
OUT_DIR = "outputs/tables"
os.makedirs(OUT_DIR, exist_ok=True)

# --------------------------------------------------------------------------
# Target QID (confirmed from Metrics PDF)
# --------------------------------------------------------------------------
TARGET_QID = "2::0::11::0_1::1::0::3::0_14::0::1::0_8"

# Verified against the rendered four-column PDF table, not only extracted text.
# Text extraction merges the eastward quantity and provider cells, displaces
# the northward quantity names, and emits a mojibake temperature unit.
VISUAL_TABLE_CORRECTIONS = {
    "4::0::4::0_1::1::0::7::0_56::0::3::0_8": {
        "quantity_name": "Vessel External Conditions Eastward Sea Water Velocity",
        "source_name": "Provider MB", "unit": "m/s",
        "label_note": "Provider and unit corrected from rendered PDF table",
    },
    "4::0::8::0_1::1::0::7::0_56::0::3::0_8": {
        "quantity_name": "Vessel External Conditions Eastward Sea Water Velocity",
        "source_name": "Provider S", "unit": "m/s",
        "label_note": "Provider and unit corrected from rendered PDF table",
    },
    "4::0::4::0_1::1::0::7::0_56::0::4::0_8": {
        "quantity_name": "Vessel External Conditions Northward Sea Water Velocity",
        "source_name": "Provider MB", "unit": "m/s",
        "label_note": "Displaced quantity label corrected from rendered PDF table",
    },
    "4::0::8::0_1::1::0::7::0_56::0::4::0_8": {
        "quantity_name": "Vessel External Conditions Northward Sea Water Velocity",
        "source_name": "Provider S", "unit": "m/s",
        "label_note": "Displaced quantity label corrected from rendered PDF table",
    },
    "4::0::8::0_1::1::0::7::0_4::0::12::0_8": {
        "unit": "C",
        "label_note": "Temperature unit normalized to C from rendered PDF table",
    },
    "2::0::11::0_1::1::0::3::0_12::0::1::0_8": {
        "unit": "",
        "label_note": "Unit unspecified in rendered source PDF; intentionally blank",
    },
}

# --------------------------------------------------------------------------
# Leakage classification rationale
#   DIRECT  = mathematically derived from target (P = τ·ω → torque × RPM)
#   PROXY   = same instrument, co-measured, strongly correlated at inference
#   SAFE    = causally upstream, available at prediction time
#   TARGET  = the prediction objective itself
# --------------------------------------------------------------------------
LEAKAGE_MAP = {
    "2::0::11::0_1::1::0::3::0_14::0::1::0_8": "TARGET",
    # Torquemeter co-measurements — same instrument:
    "2::0::11::0_1::1::0::3::0_12::0::2::0_8": "DIRECT",   # Shaft Torque (τ·ω = P)
    "2::0::11::0_1::1::0::3::0_15::0::1::0_8": "DIRECT",   # Shaft Mechanical Energy (cumulative integral of P)
    "2::0::11::0_1::1::0::3::0_17::0::1::0_8": "DIRECT",   # Shaft Thrust Force (derived alongside P)
    "2::0::11::0_1::1::0::3::0_12::0::1::0_8": "DIRECT",   # Shaft Revolutions (same torquemeter instrument)
    # RPM from torquemeter — note: RPM alone does not equal P, but is co-measured on same torquemeter.
    # Combined torque+RPM = P, so torquemeter-sourced RPM is a direct leakage proxy at that instrument.
    "2::0::11::0_1::1::0::3::0_1::0::6::0_8": "DIRECT",    # Propeller Shaft RPM (Torquemeter)
    # Fuel mass flow measured by torquemeter — co-instrument, not a causal input available for route planning:
    "2::0::11::0_1::2::0::8::0_22::0::1::1_8": "PROXY",    # ME Fuel Oil Inlet Mass Flow (Torquemeter)
}

FEATURE_GROUPS = {
    # Engine (transducer / CAMS — not torquemeter)
    "1::0::14::0_1::2::0::8::0_3::0::3::0_8":  "engine",
    "1::0::15::0_1::2::0::3::0_1::0::6::0_8":  "engine",
    "1::0::25::0_1::2::0::8::0_20::0::1::0_8": "engine",
    "2::0::25::0_1::2::0::3::0_1::0::6::0_8":  "engine",
    "3::0::1::0_1::2::0::8::0_1::0::6::0_8":   "engine",
    # Motion / navigation
    "2::0::5::0_1::1::0::2::0_2::0::8::21_8":  "motion",
    "2::0::5::0_1::1::0::2::0_6::0::1::0_8":   "motion",
    "2::0::6::1_1::1::0::2::0_1::0::1::0_8":   "motion",
    "2::0::7::0_1::1::0::2::0_1::0::5::11_8":  "motion",
    # Loading / hull
    "3::0::1::0_1::1::0::2::0_11::0::1::0_8":  "loading",
    "3::0::1::0_1::1::0::2::0_11::0::2::0_8":  "loading",
    "3::0::1::0_1::1::0::2::0_11::0::3::0_8":  "loading",
    "3::0::1::0_1::1::0::2::0_11::0::4::0_8":  "loading",
    "2::0::4::0_1::1::0::2::0_37::0::2::0_8":  "loading",
    # Wind (on-board anemometer)
    "2::0::1::0_1::1::0::7::0_1::0::4::22_8":  "wind_obs",
    "2::0::1::0_1::1::0::7::0_2::0::15::22_8": "wind_obs",
    # Environmental — Provider MB
    "4::0::4::0_1::1::0::7::0_1::0::4::21_8":  "env_mb",
    "4::0::4::0_1::1::0::7::0_2::0::15::21_8": "env_mb",
    "4::0::4::0_1::1::0::7::0_45::0::1::0_8":  "env_mb",
    "4::0::4::0_1::1::0::7::0_45::0::2::0_8":  "env_mb",
    "4::0::4::0_1::1::0::7::0_56::0::3::0_8":  "env_mb",
    "4::0::4::0_1::1::0::7::0_56::0::4::0_8":  "env_mb",
    # Environmental — Provider S
    "4::0::8::0_1::1::0::7::0_2::0::18::21_8": "env_s",
    "4::0::8::0_1::1::0::7::0_4::0::12::0_8":  "env_s",
    "4::0::8::0_1::1::0::7::0_40::0::2::0_8":  "env_s",
    "4::0::8::0_1::1::0::7::0_45::0::1::0_8":  "env_s",
    "4::0::8::0_1::1::0::7::0_56::0::3::0_8":  "env_s",
    "4::0::8::0_1::1::0::7::0_56::0::4::0_8":  "env_s",
    "4::0::8::0_1::1::0::7::0_56::0::5::0_8":  "env_s",
    "4::0::8::0_1::1::0::7::0_56::0::6::0_8":  "env_s",
    # Torquemeter co-measurements (leakage)
    "2::0::11::0_1::1::0::3::0_14::0::1::0_8": "target",
    "2::0::11::0_1::1::0::3::0_12::0::2::0_8": "torquemeter_leakage",
    "2::0::11::0_1::1::0::3::0_15::0::1::0_8": "torquemeter_leakage",
    "2::0::11::0_1::1::0::3::0_17::0::1::0_8": "torquemeter_leakage",
    "2::0::11::0_1::1::0::3::0_12::0::1::0_8": "torquemeter_leakage",
    "2::0::11::0_1::1::0::3::0_1::0::6::0_8":  "torquemeter_leakage",
    "2::0::11::0_1::2::0::8::0_22::0::1::1_8": "torquemeter_leakage",
}

# --------------------------------------------------------------------------
# Parse Metrics Registration PDF
# --------------------------------------------------------------------------
def parse_metrics_pdf(pdf_path: str) -> list:
    """
    Extract QID mappings from the Metrics Registration PDF.
    The PDF layout has 4 columns: qid_mapping, quantity_name, source_name, unit.
    Records are parsed by detecting QID patterns (contain '::' and '_').
    Returns list of dicts with those 4 fields.
    """
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n---PAGE_BREAK---\n"

    # Tokenise: split on newlines, strip whitespace, remove blanks
    tokens = [t.strip() for t in full_text.splitlines() if t.strip()]

    # A QID token matches the pattern: digits::digits::digits::digits_...
    qid_pattern = re.compile(r'^\d+::\d+::\d+::\d+_.+_\d+$')

    records = []
    i = 0
    while i < len(tokens):
        if qid_pattern.match(tokens[i]):
            qid = tokens[i]
            # The next tokens should be: quantity_name, source_name, unit
            # But the PDF text extraction may split differently — collect
            # up to 3 non-QID tokens
            parts = []
            j = i + 1
            while j < len(tokens) and len(parts) < 4:
                if tokens[j] in ("---PAGE_BREAK---", "qid_mapping", "quantity_name", "source_name", "unit"):
                    break
                if qid_pattern.match(tokens[j]):
                    break
                parts.append(tokens[j])
                j += 1

            # Map parts to fields — PDF order: quantity_name, source_name, unit
            # Some entries span 2 lines (name wrapped), so be flexible
            quantity_name = parts[0] if len(parts) > 0 else ""
            source_name   = parts[1] if len(parts) > 1 else ""
            unit          = parts[2] if len(parts) > 2 else ""
            # Sometimes source_name and quantity_name are swapped in PDF text
            # Check: source always starts with known prefixes
            known_sources = {"Transducer", "Instrument", "Control", "Provider"}
            if source_name and not any(source_name.startswith(s) for s in known_sources):
                # Likely extra quantity_name line; concatenate and shift
                if len(parts) > 2:
                    quantity_name = parts[0] + " " + parts[1]
                    source_name   = parts[2]
                    unit          = parts[3] if len(parts) > 3 else ""

            records.append({
                "qid": qid,
                "quantity_name": quantity_name,
                "source_name": source_name,
                "unit": unit,
                "raw_context": " | ".join(parts[:5])
            })
            i = j
        else:
            i += 1

    return records

# --------------------------------------------------------------------------
# Load QID presence matrix from audit
# --------------------------------------------------------------------------
def load_qid_presence(qid_per_file_path: str):
    """Returns (all_qids, jan25_qids, monthly_qids, file_list)."""
    if not os.path.exists(qid_per_file_path):
        print(f"WARNING: {qid_per_file_path} not found. Run 00_schema_audit.py first.")
        return set(), set(), set(), []

    with open(qid_per_file_path, "r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        files = [f for f in reader.fieldnames if f != "qid"]
        monthly_files = [f for f in files if f != "Jan25.csv"]
        all_qids = set()
        jan25_qids = set()
        monthly_qids = set()
        for row in reader:
            qid = row["qid"]
            all_qids.add(qid)
            if row.get("Jan25.csv") == "1":
                jan25_qids.add(qid)
            if any(row.get(f) == "1" for f in monthly_files):
                monthly_qids.add(qid)

    return all_qids, jan25_qids, monthly_qids, files


def load_verified_datatypes(observed_qids: set[str]) -> dict[str, str]:
    """Use the full-file numeric audit to assign parsed sensor-value types.

    Raw CSV fields are text. Script 02 parses each sensor value with Python
    float (binary64) and counts non-numeric/non-finite values as missing.
    A missing or stale audit must not turn a PDF-only QID into an observed
    numeric sensor or silently certify a changed raw export.
    """
    if not os.path.exists(QUALITY_SUMMARY):
        raise FileNotFoundError(f"{QUALITY_SUMMARY} is required; run scripts/02_quality_audit.py first")
    evidence_qids = set()
    audited_rows = 0
    with open(QUALITY_SUMMARY, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            qid = row["qid"]
            evidence_qids.add(qid)
            numeric = int(row["n_numeric"])
            missing = int(row["n_missing"])
            total = int(row["n_total"])
            if numeric <= 0 or missing != 0 or numeric + missing != total:
                raise ValueError(f"Sensor values not fully verified numeric for {row['file']} / {qid}")
            audited_rows += total
    if evidence_qids != observed_qids:
        raise ValueError(f"QID mismatch between quality and presence audits: "
                         f"quality_only={evidence_qids-observed_qids}, presence_only={observed_qids-evidence_qids}")
    with open(DATA_INVENTORY, "r", encoding="utf-8", newline="") as fh:
        inventory_rows = sum(int(row["row_count"]) for row in csv.DictReader(fh))
    if audited_rows != inventory_rows:
        raise ValueError(f"Quality audit covers {audited_rows} rows, inventory has {inventory_rows}")
    return {qid: "numeric (float64 parsed from CSV text)" for qid in observed_qids}

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("DATA DICTIONARY + QID RECONCILIATION")
    print("=" * 70)

    # 1. Parse Metrics PDF
    print("\n[Step 1] Parsing Metrics Registration PDF ...")
    pdf_records = parse_metrics_pdf(PDF_PATH)
    if len({record["qid"] for record in pdf_records}) != len(pdf_records):
        raise ValueError("Duplicate QIDs extracted from Metrics registration PDF")
    for record in pdf_records:
        correction = VISUAL_TABLE_CORRECTIONS.get(record["qid"], {})
        record.update({key: value for key, value in correction.items() if key != "label_note"})
    print(f"  Extracted {len(pdf_records)} records from PDF")

    pdf_qids = {r["qid"] for r in pdf_records}

    # 2. Load observed QIDs
    print("\n[Step 2] Loading QID presence matrix from schema audit ...")
    all_qids, jan25_qids, monthly_qids, file_list = load_qid_presence(QID_PER_FILE)
    verified_datatypes = load_verified_datatypes(all_qids)
    print(f"  QIDs observed in 1.csv–12.csv:  {len(monthly_qids)}")
    print(f"  QIDs observed in Jan25.csv:     {len(jan25_qids)}")
    print(f"  Total unique QIDs in any file:  {len(all_qids)}")

    # 3. Reconciliation
    in_pdf_and_data = pdf_qids & all_qids
    in_pdf_not_data = pdf_qids - all_qids
    in_data_not_pdf = all_qids - pdf_qids
    absent_jan25    = monthly_qids - jan25_qids

    print(f"\n[Step 3] Reconciliation:")
    print(f"  Registered in PDF:                           {len(pdf_qids)}")
    print(f"  In PDF AND observed in data:                 {len(in_pdf_and_data)}")
    print(f"  In PDF but NOT observed in any CSV:          {len(in_pdf_not_data)}")
    print(f"  Observed in CSVs but NOT in PDF:             {len(in_data_not_pdf)}")
    print(f"  In 1.csv–12.csv but ABSENT from Jan25.csv:  {len(absent_jan25)}")

    if in_pdf_not_data:
        print("\n  QIDs in PDF not found in data:")
        for q in sorted(in_pdf_not_data): print(f"    {q}")
    if in_data_not_pdf:
        print("\n  QIDs in data not in PDF:")
        for q in sorted(in_data_not_pdf): print(f"    {q}")

    # Target availability check
    print(f"\n[Step 4] Target QID availability check:")
    print(f"  Target QID: {TARGET_QID}")
    print(f"  In PDF:          {TARGET_QID in pdf_qids}")
    print(f"  In 1.csv–12.csv: {TARGET_QID in monthly_qids}")
    print(f"  In Jan25.csv:    {TARGET_QID in jan25_qids}")

    if TARGET_QID in jan25_qids:
        print("  -> Jan25.csv CONTAINS target labels (usable as eval set IF target is valid)")
    else:
        print("  -> Jan25.csv DOES NOT CONTAIN target labels — cannot be used as labelled eval set")

    # 4. Build data dictionary
    pdf_lookup = {r["qid"]: r for r in pdf_records}
    all_combined_qids = pdf_qids | all_qids

    dict_rows = []
    for qid in sorted(all_combined_qids):
        pdf_rec = pdf_lookup.get(qid, {})
        leakage = LEAKAGE_MAP.get(qid, "none")
        fgroup  = FEATURE_GROUPS.get(qid, "unclassified")
        if qid not in CHANNELS:
            modelling_role = "not_observed"
        else:
            column = CHANNELS[qid][0]
            if column == TARGET_COLUMN:
                modelling_role = "target"
            elif column in LEAKAGE:
                modelling_role = "excluded_torquemeter"
            elif column in DRAFT:
                modelling_role = "excluded_constant_zero_draft"
            elif column == "HULL_WaterDepth_m":
                modelling_role = "excluded_no_october_overlap"
            elif column in MODEL_CANDIDATES:
                modelling_role = "candidate"
            else:
                raise ValueError(f"Unclassified channel: {qid}")
        dict_rows.append({
            "qid":                qid,
            "quantity_name":      pdf_rec.get("quantity_name", "UNKNOWN"),
            "source_name":        pdf_rec.get("source_name", "UNKNOWN"),
            "data_type":          verified_datatypes.get(qid, "not_observed"),
            "unit":               pdf_rec.get("unit", "UNKNOWN"),
            "leakage_risk":       leakage,
            "feature_group":      fgroup,
            "modelling_role":     modelling_role,
            "in_pdf":             "yes" if qid in pdf_qids else "no",
            "in_monthly_12":      "yes" if qid in monthly_qids else "no",
            "in_jan25":           "yes" if qid in jan25_qids else "no",
            "raw_pdf_context":    pdf_rec.get("raw_context", ""),
            "label_note":         VISUAL_TABLE_CORRECTIONS.get(qid, {}).get("label_note", ""),
        })

    # Write data dictionary
    dict_path = os.path.join(OUT_DIR, "data_dictionary.csv")
    fields = ["qid","quantity_name","source_name","data_type","unit","leakage_risk","feature_group",
              "modelling_role","in_pdf","in_monthly_12","in_jan25","raw_pdf_context","label_note"]
    with open(dict_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(dict_rows)

    # Write reconciliation summary
    recon_path = os.path.join(OUT_DIR, "qid_reconciliation.csv")
    recon_rows = [
        {"category": "Registered in Metrics PDF", "count": len(pdf_qids)},
        {"category": "In PDF AND observed in 1.csv-12.csv", "count": len(in_pdf_and_data & monthly_qids)},
        {"category": "In PDF AND observed in Jan25.csv", "count": len(in_pdf_and_data & jan25_qids)},
        {"category": "In PDF but not observed in any file", "count": len(in_pdf_not_data)},
        {"category": "Observed in files but not in PDF", "count": len(in_data_not_pdf)},
        {"category": "In 1.csv-12.csv but absent from Jan25.csv", "count": len(absent_jan25)},
        {"category": "Target QID in PDF", "count": int(TARGET_QID in pdf_qids)},
        {"category": "Target QID in 1.csv-12.csv", "count": int(TARGET_QID in monthly_qids)},
        {"category": "Target QID in Jan25.csv", "count": int(TARGET_QID in jan25_qids)},
    ]
    with open(recon_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["category","count"])
        w.writeheader()
        w.writerows(recon_rows)

    print(f"\nOutputs written:")
    print(f"  {dict_path}")
    print(f"  {recon_path}")

if __name__ == "__main__":
    main()
