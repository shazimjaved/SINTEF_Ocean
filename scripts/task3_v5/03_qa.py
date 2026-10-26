"""Independent, executable checks for physical-reference/loading diagnostics.

Run: python -X utf8 scripts/task3_v5/03_qa.py
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import fitz
import openpyxl
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "task3_v5"
PDF = ROOT / "docs" / "vessel" / "TOWING TANK MODEL TEST REPORT for A 76000DWT Bulk Carrier with&without PSV.pdf"
NOON_AUG = ROOT / "data" / "Noon Reports" / "N08_August_Data_with_Propulsion_and_Fuel.csv"
checks = []


def check(check_id: str, assertion: bool, evidence: str) -> None:
    checks.append({"check_id": check_id, "status": "PASS" if assertion else "FAIL", "evidence": evidence})


def main() -> None:
    curves = pd.read_csv(OUT / "tow_tank_with_psv_tables.csv")
    source = fitz.open(PDF)
    check("V5_REF_01", len(curves) == 36 and curves.table_number.nunique() == 4
          and curves.groupby("table_number").size().eq(9).all(),
          "36 extracted rows, four source tables, nine rows each")
    # Independent source-page anchors, including the Table 25 heading conflict.
    expected = [(24, 7, "design", 11.5, 3295, 15.5, 9231),
                (32, 13, "scantling", 11.0, 3327, 15.0, 9359),
                (40, 19, "ballast", 12.0, 3059, 16.0, 9074),
                (48, 25, "heavy_ballast", 12.0, 3249, 16.0, 9294)]
    for page, table, condition, first_speed, first_kw, last_speed, last_kw in expected:
        x = curves[curves.table_number.eq(table)].sort_values("speed_kn")
        body = source[page - 1].get_text()
        ok = (len(x) == 9 and x.loading_condition.eq(condition).all()
              and x.iloc[0].speed_kn == first_speed and x.iloc[0].delivered_propeller_power_kw == first_kw
              and x.iloc[-1].speed_kn == last_speed and x.iloc[-1].delivered_propeller_power_kw == last_kw
              and str(first_kw) in body and str(last_kw) in body and "PSV" in body)
        check(f"V5_REF_{table:02d}", ok, f"PDF page {page}, Table {table} endpoints and PSV appendage")
    p48 = source[47].get_text()
    check("V5_REF_25_HEADING", "WITHOUT PSV" in p48 and "PSV" in p48.split("Appendage")[-1]
          and "Table  25" in p48 and "3249" in source[13].get_text()
          and "9294" in source[13].get_text(),
          "Table 25 heading conflicts with PSV appendage; summary page 14 confirms its with-PSV endpoints")
    table19 = curves[curves.table_number.eq(19) & curves.speed_kn.eq(13)]
    check("V5_REF_19_ROUNDING", len(table19) == 1 and table19.delivered_propeller_power_kw.iloc[0] == 4042
          and "4041" in source[12].get_text(),
          "PDF summary page 13 says 4041 kW at 13 kn; primary Table 19 says 4042 kW")
    comparison = pd.read_csv(OUT / "engine_reference_comparison.csv")
    book = openpyxl.load_workbook(ROOT / "docs" / "vessel" / "Particulars.xlsx",
                                  read_only=True, data_only=True)
    check("V5_SPEC_01", comparison.smcr_kw.tolist() == [8833, 8833, 9500, 9500]
          and book.active["C71"].value == 9500
          and "9500 kW x 105" in source[7].get_text(),
          "GA and sea-trial 8833 visually inspected; particulars/PDF 9500 independently checked")
    august_noon = pd.read_csv(NOON_AUG)
    unit = pd.read_csv(OUT / "displacement_unit_evidence.csv")
    check("V5_NOON_01", len(august_noon) == 31 and august_noon.Displacement.nunique() == 1
          and august_noon.Displacement.iloc[0] == 89145
          and not any("(" in c or "[" in c for c in august_noon.columns if "Displacement" in c)
          and "not stated" in unit.loc[unit.reference.eq("reported August displacement"), "unit"].iloc[0],
          "August source has 31 values of 89145 and no unit in Displacement header")
    check("V5_NOON_02", book.active["D26"].value == 86941
          and math.isclose(86941 * 1.025, 89114.525, abs_tol=.001)
          and math.isclose(89145 - 86941 * 1.025, 30.475, abs_tol=.001),
          "Assumed 1.025 t/m3 gives 89114.525 t; difference 30.475")
    month = pd.read_csv(OUT / "monthly_loading_power_coverage.csv")
    check("V5_PERIOD_01", month.month.tolist() == list(range(1, 11))
          and len(month) == 10 and month.minute_rows.sum() == 305 * 1440,
          "Only Jan-Oct minute records; July remains a descriptive quarantine")
    check("V5_SCOPE_01", (month.positive_minutes + month.recorded_zero_forward_minutes
          + month.negative_or_mixed_forward_minutes == month.forward_minutes).all()
          and month.loc[month.month.eq(8), "positive_minutes"].iloc[0] == 35086
          and month.loc[month.month.eq(8), "recorded_zero_forward_minutes"].iloc[0] == 6030,
          "Positive, zero and negative/mixed forward counts reconcile")
    daily = pd.read_csv(OUT / "daily_retrospective_loading.csv")
    check("V5_DATE_01", len(daily) == 305 and daily.date.is_unique
          and daily.loc[daily.month.eq(8), "noon_displacement_unit_unspecified"].eq(89145).all(),
          "Minute windows assigned by end minus one minute; 305 distinct source calendar dates")
    check("V5_LOAD_01", daily.loc[daily.month.eq(8), "loading_reference"].eq("scantling").all()
          and ~daily.loc[daily.month.le(6), "loading_reference"].eq("scantling").any(),
          "Under declared proximity rule, August 31 scantling-like days, Jan-Jun zero")
    zero_end = daily[daily.date.isin([f"2024-08-{day:02d}" for day in range(28, 32)])]
    check("V5_ZERO_01", len(zero_end) == 4 and zero_end.recorded_zero_minutes.eq(1440).all()
          and zero_end.positive_minutes.eq(0).all()
          and zero_end.noon_displacement_unit_unspecified.eq(89145).all(),
          "Four full August zero-power days coexist with unchanged reported Noon displacement")
    bin_rows = pd.read_csv(OUT / "loading_speed_power_bins.csv")
    check("V5_BINS_01", (bin_rows.n_positive + bin_rows.n_zero <= bin_rows.n_forward).all()
          and bin_rows.loc[bin_rows.month.eq(8), "n_positive"].sum() == 35086,
          "Speed bins reconcile to monthly scopes")
    pairs = pd.read_csv(OUT / "august_earlier_operating_matches.csv.gz")
    summary = pd.read_csv(OUT / "august_earlier_match_summary.csv")
    x = pairs[pairs.normalized_feature_distance.le(1)]
    s = summary.iloc[0]
    check("V5_MATCH_01", len(pairs) == 3517 and len(x) == s.matched_n
          and math.isclose(x.power_difference_august_minus_earlier_kw.median(),
                           s.median_power_difference_kw, abs_tol=.01)
          and (x.august_loading_reference != x.earlier_loading_reference).all(),
          "Independent matched-pair recomputation and zero same-load analogues")
    same = pd.read_csv(OUT / "september_august_same_load_matches.csv.gz")
    same_summary = pd.read_csv(OUT / "september_august_same_load_match_summary.csv")
    sm = same[same.normalized_feature_distance.le(1)]
    ss = same_summary.iloc[0]
    check("V5_MATCH_02", len(same) == 1685 and len(sm) == ss.matched_n
          and math.isclose(sm.september_minus_august_power_kw.median(),
                           ss.median_september_minus_august_kw, abs_tol=.01)
          and sm.september_noon_displacement_unit_unspecified.eq(
              sm.august_noon_displacement_unit_unspecified).all(),
          "September-August positive-state matches recomputed; identical reported Noon displacement")
    ratio = pd.read_csv(OUT / "reference_ratio_loading_summary.csv")
    aug = ratio[(ratio.period == "August") & (ratio.loading_reference == "scantling")].iloc[0]
    check("V5_RATIO_01", aug.days == 31 and aug.reference_days_ge30 ==
          ((daily.month.eq(8)) & (daily.reference_covered_positive_minutes.ge(30))).sum()
          and aug.reference_covered_positive_minutes < aug.positive_minutes,
          "Ratio coverage is explicitly limited to in-range speeds and >=30/day for daily median")
    # The source directory restriction is deliberate: neither December nor
    # illustrative templates are input to the scripts.
    scripts = "\n".join((ROOT / "scripts" / "task3_v5" / name).read_text(encoding="utf-8")
                        for name in ["01_physical_references.py", "02_loading_diagnostics.py"])
    check("V5_PROVENANCE_01", "docs/Templetes/" not in scripts
          and "minute_2024_12" not in scripts and month.month.max() == 10,
          "No template CSV or December minute file is an input")
    with (OUT / "v5_qa.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["check_id", "status", "evidence"])
        w.writeheader()
        w.writerows(checks)
    for row in checks:
        print(row["status"], row["check_id"], row["evidence"])
    failures = [r for r in checks if r["status"] == "FAIL"]
    print(f"{len(checks) - len(failures)} PASS; {len(failures)} FAIL")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
