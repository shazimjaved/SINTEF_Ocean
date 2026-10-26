"""Extract source-verified with-PSV tow-tank curves; never use template CSV data.

Run from the project root: python -X utf8 scripts/task3_v5/01_physical_references.py
"""
from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path

import fitz
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import openpyxl


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "task3_v5"
PDF = ROOT / "docs" / "vessel" / "TOWING TANK MODEL TEST REPORT for A 76000DWT Bulk Carrier with&without PSV.pdf"
PARTICULARS = ROOT / "docs" / "vessel" / "Particulars.xlsx"
COLUMNS = ["speed_kn", "thrust_deduction", "wake_fraction", "hull_efficiency",
           "relative_rotative_efficiency", "open_water_efficiency",
           "propulsive_efficiency", "effective_power_kw", "delivered_propeller_power_kw",
           "propeller_rpm"]
SPECS = [
    (24, 7, "design", 12.20, 12.20, 73346),
    (32, 13, "scantling", 14.25, 14.25, 86941),
    (40, 19, "ballast", 5.00, 7.80, 36134),
    (48, 25, "heavy_ballast", 4.40, 9.40, 39024),
]


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(PDF)
    digest = hashlib.sha256(PDF.read_bytes()).hexdigest()
    rows = []
    meta = []
    for page_no, table_no, condition, fore, aft, volume in SPECS:
        txt = doc[page_no - 1].get_text()
        compact = [s.strip() for s in txt.splitlines() if s.strip()]
        assert re.search(rf"Table\s+{table_no}\b", txt)
        assert "PSV" in compact[compact.index("Appendage") + 2:compact.index("Appendage") + 8], (page_no, "PSV absent")
        head = next(i for i, x in enumerate(compact) if x.startswith("NT(rpm)"))
        numbers = []
        for item in compact[head + 1:]:
            if not re.fullmatch(r"-?\d+(?:\.\d+)?", item):
                break
            numbers.append(float(item))
        assert len(numbers) == 90, (page_no, len(numbers))
        parsed = [numbers[i:i + 10] for i in range(0, 90, 10)]
        assert all(parsed[i][0] < parsed[i + 1][0] for i in range(8))
        assert all(parsed[i][8] < parsed[i + 1][8] for i in range(8))
        for values in parsed:
            row = dict(zip(COLUMNS, values))
            row.update(loading_condition=condition, pdf_page=page_no,
                       report_page=page_no - 1, table_number=table_no,
                       fore_draft_m=fore, aft_draft_m=aft,
                       displacement_volume_m3=volume,
                       appendage="with PSV", sea_condition="calm sea; sufficient depth; clean bottom",
                       source_pdf_sha256=digest)
            rows.append(row)
        meta.append(dict(loading_condition=condition, pdf_page=page_no,
                         report_page=page_no - 1, table_number=table_no,
                         n_rows=len(parsed), min_speed_kn=parsed[0][0],
                         max_speed_kn=parsed[-1][0],
                         min_delivered_kw=parsed[0][8], max_delivered_kw=parsed[-1][8],
                         fore_draft_m=fore, aft_draft_m=aft,
                         displacement_volume_m3=volume,
                         power_definition="PDT corrected delivered power at propeller, not measured shaft power",
                         caveat=("Table 25 heading says WITHOUT PSV, but appendage/summary say with PSV"
                                 if table_no == 25 else
                                 "PDF summary page 13 says 4041 kW at 13 kn; Table 19 says 4042 kW"
                                 if table_no == 19 else "")))
    assert len(rows) == 36 and {m["table_number"] for m in meta} == {7, 13, 19, 25}
    assert [(r["speed_kn"], r["delivered_propeller_power_kw"]) for r in rows
            if r["loading_condition"] == "heavy_ballast" and r["speed_kn"] in (12, 16)] == [(12.0, 3249.0), (16.0, 9294.0)]
    write_csv(OUT / "tow_tank_with_psv_tables.csv", rows,
              ["loading_condition", "pdf_page", "report_page", "table_number", *COLUMNS,
               "fore_draft_m", "aft_draft_m", "displacement_volume_m3", "appendage",
               "sea_condition", "source_pdf_sha256"])
    write_csv(OUT / "tow_tank_source_summary.csv", meta, list(meta[0]))

    book = openpyxl.load_workbook(PARTICULARS, read_only=True, data_only=True)
    sheet = book.active
    assert sheet["C71"].value == 9500 and sheet["E71"].value == 105
    assert sheet["D26"].value == 86941 and sheet["D27"].value == 14.25
    assert sheet["D76"].value == 6.8 and sheet["D79"].value == 4
    # GA and Sea Trials are images, independently inspected visually; their
    # values are transcribed here rather than falsely represented as OCR output.
    comparison = [
        dict(source="GA.jpg principal particulars (visual)", engine="MAN B&W 5S60MC-C Mark VII-tier II", smcr_kw=8833, smcr_rpm=105, transmission_efficiency="unspecified", propeller="unspecified in principal particulars"),
        dict(source="Sea_Trials_curves.jpg graph (visual)", engine="8833 kW reference, engine model not labelled", smcr_kw=8833, smcr_rpm="unspecified", transmission_efficiency="0.985 factor shown in DHP annotation", propeller="model/measured design and ballast curves; PSV detail not labelled on graph"),
        dict(source="Particulars.xlsx Sheet1 row 71, 75-80", engine="engine model unspecified", smcr_kw=9500, smcr_rpm=105, transmission_efficiency="unspecified", propeller="6.8 m, 4 blades, pitch ratio 0.6742, right-handed"),
        dict(source="Towing report PDF p8 (report p7)", engine="Wartsila 5RT-flex58T-D", smcr_kw=9500, smcr_rpm=105, transmission_efficiency="0.99", propeller="TM1747A; 6.8 m, 4 blades, pitch ratio 0.6742, right-handed"),
    ]
    write_csv(OUT / "engine_reference_comparison.csv", comparison, list(comparison[0]))
    assert 9500 - 8833 == 667
    fig, ax = plt.subplots(figsize=(8, 5.1))
    for condition, color in [("design", "#1f77b4"), ("scantling", "#d62728"),
                             ("ballast", "#2ca02c"), ("heavy_ballast", "#9467bd")]:
        data = [r for r in rows if r["loading_condition"] == condition]
        ax.plot([r["speed_kn"] for r in data], [r["delivered_propeller_power_kw"] for r in data],
                marker="o", lw=1.6, ms=3.2, color=color, label=condition.replace("_", " "))
    ax.set(xlabel="Speed through water (kn)", ylabel="Corrected delivered power at propeller, PDT (kW)",
           title="Towing-tank predictions with PSV: calm water, clean hull")
    ax.grid(alpha=.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "tow_tank_with_psv_curves.png", dpi=180)
    plt.close(fig)
    print("PASS: extracted 36 source-table rows; four loading conditions; source/spec checks")


if __name__ == "__main__":
    main()
