"""Numeric and cross-source QA gate for preliminary Tasks 1 and 2.

Writes a checklist before returning a non-zero exit code on any FAIL. A PASS
states only the precise assertion checked; it is not a scientific endorsement.
"""

import csv
import runpy
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
from channel_config import ANGLE_COLUMNS, CHANNELS, COLUMN_TO_SOURCE, DRAFT, ENVIRONMENTAL, LEAKAGE, MODEL_CANDIDATES, TARGET

ROOT = Path(".")
TABLES = ROOT / "outputs/tables"
REPORTS = ROOT / "outputs/reports"
items = []


def check(area, claim, passed, evidence, corrective_action="Investigate and regenerate the affected output"):
    items.append({
        "id": f"Q{len(items)+1:02d}", "area": area, "claim": claim,
        "status": "PASS" if passed else "FAIL", "evidence": str(evidence),
        "action_required": "" if passed else corrective_action,
    })


def unresolved(area, claim, evidence, action):
    items.append({
        "id": f"Q{len(items)+1:02d}", "area": area, "claim": claim,
        "status": "UNRESOLVED", "evidence": evidence, "action_required": action,
    })


def main():
    inventory = pd.read_csv(TABLES / "data_inventory.csv").set_index("file")
    duplicate = pd.read_csv(TABLES / "duplicate_audit_yearwide.csv").set_index("file")
    monthly_files = [f"{m}.csv" for m in range(1, 13)]
    check("inventory", "2024 and all-file physical row counts match independent duplicate scan",
          int(inventory.loc[monthly_files, "row_count"].sum()) == 41079968
          and int(inventory.row_count.sum()) == 42192373
          and (inventory.row_count.sort_index() == duplicate.physical_rows.sort_index()).all(),
          f"2024={int(inventory.loc[monthly_files, 'row_count'].sum())}; "
          f"all={int(inventory.row_count.sum())}")
    check("duplicates", "Exact per-file timestamp/QID audit found no duplicate keys or malformed short rows",
          duplicate.duplicate_keys.sum() == 0 and duplicate.malformed_short_rows.sum() == 0
          and (duplicate.unique_timestamp_qid_pairs + duplicate.extra_duplicate_rows
               + duplicate.malformed_short_rows == duplicate.physical_rows).all(),
          f"duplicate_keys={int(duplicate.duplicate_keys.sum())}; "
          f"malformed_short_rows={int(duplicate.malformed_short_rows.sum())}",
          "Inspect duplicate report and specify a deterministic resolution rule")
    check("duplicates", "2024 file timestamp ranges are confined to distinct named calendar months",
          all(str(inventory.loc[f"{m}.csv", "ts_overall_min"]).startswith(f"2024-{m:02d}-")
              and str(inventory.loc[f"{m}.csv", "ts_overall_max"]).startswith(f"2024-{m:02d}-")
              for m in range(1, 13)),
          "Per-file min/max ISO timestamp prefixes checked for all 12 months")

    rec = pd.read_csv(TABLES / "qid_reconciliation.csv").set_index("category")["count"]
    check("QIDs", "37 PDF QIDs, 36 observed in 2024, 26 in Jan25, target absent in Jan25",
          int(rec["Registered in Metrics PDF"]) == 37
          and int(rec["In PDF AND observed in 1.csv-12.csv"]) == 36
          and int(rec["In PDF AND observed in Jan25.csv"]) == 26
          and int(rec["Target QID in Jan25.csv"]) == 0,
          rec.to_dict())
    dictionary = pd.read_csv(TABLES / "data_dictionary.csv", keep_default_na=False)
    qids = dictionary.qid
    check("dictionary", "All 37 registered QIDs are unique; exactly 36 are observed in 2024",
          len(dictionary) == 37 and qids.is_unique
          and int((dictionary.in_pdf == "yes").sum()) == 37
          and int((dictionary.in_monthly_12 == "yes").sum()) == 36,
          f"rows={len(dictionary)}; unique={qids.nunique()}; "
          f"2024={int((dictionary.in_monthly_12 == 'yes').sum())}")
    dictionary = dictionary.set_index("qid")
    north_qids = ["4::0::4::0_1::1::0::7::0_56::0::4::0_8",
                  "4::0::8::0_1::1::0::7::0_56::0::4::0_8"]
    north = dictionary.loc[north_qids]
    check("dictionary", "Both northward-current quantity labels and provider sources are explicit",
          north.quantity_name.str.contains("Northward Sea Water Velocity").all()
          and set(north.source_name) == {"Provider MB", "Provider S"},
          north[["quantity_name", "source_name"]].to_dict("records"))
    east_qids = ["4::0::4::0_1::1::0::7::0_56::0::3::0_8",
                 "4::0::8::0_1::1::0::7::0_56::0::3::0_8"]
    east = dictionary.loc[east_qids]
    check("dictionary", "Eastward sea-water currents have Provider MB/S sources and m/s units",
          east.quantity_name.eq("Vessel External Conditions Eastward Sea Water Velocity").all()
          and list(east.source_name) == ["Provider MB", "Provider S"]
          and east.unit.eq("m/s").all(),
          east[["quantity_name", "source_name", "unit"]].to_dict("records"))
    temp_qid = "4::0::8::0_1::1::0::7::0_4::0::12::0_8"
    check("dictionary", "Provider S sea-water temperature unit is normalized to C",
          dictionary.loc[temp_qid, "source_name"] == "Provider S"
          and dictionary.loc[temp_qid, "unit"] == "C",
          dictionary.loc[temp_qid, ["source_name", "unit"]].to_dict())
    revol_qid = "2::0::11::0_1::1::0::3::0_12::0::1::0_8"
    empty_units = set(dictionary.index[dictionary.unit.str.strip() == ""])
    check("dictionary", "Only shaft revolutions has an intentionally unspecified unit, documented from the PDF",
          empty_units == {revol_qid}
          and dictionary.loc[revol_qid, "source_name"] == "Instrument Torquemeter"
          and "unspecified" in dictionary.loc[revol_qid, "label_note"].lower(),
          f"empty-unit QIDs={sorted(empty_units)}; note={dictionary.loc[revol_qid, 'label_note']}")
    check("dictionary", "No source field is empty or UNKNOWN",
          dictionary.source_name.str.strip().ne("").all()
          and dictionary.source_name.ne("UNKNOWN").all(),
          f"empty={int(dictionary.source_name.str.strip().eq('').sum())}; "
          f"UNKNOWN={int(dictionary.source_name.eq('UNKNOWN').sum())}")
    provider_mb_qids = [qid for qid, (_, source) in CHANNELS.items() if source == "provider_mb"]
    provider_s_qids = [qid for qid, (_, source) in CHANNELS.items() if source == "provider_s"]
    check("dictionary", "All 14 provider QIDs retain their explicit Provider MB/S source",
          len(provider_mb_qids) == 6 and len(provider_s_qids) == 8
          and dictionary.loc[provider_mb_qids, "source_name"].eq("Provider MB").all()
          and dictionary.loc[provider_s_qids, "source_name"].eq("Provider S").all(),
          f"MB={len(provider_mb_qids)}; S={len(provider_s_qids)}")
    roles = dictionary[dictionary.in_monthly_12 == "yes"].modelling_role.value_counts()
    check("features", "2024 channels classify as 24 candidates, 14 external sources, six torquemeter exclusions and four faulty drafts",
          roles.get("candidate", 0) == 24 and roles.get("excluded_torquemeter", 0) == 6
          and roles.get("excluded_constant_zero_draft", 0) == 4
          and len(ENVIRONMENTAL) == 14 and len(MODEL_CANDIDATES) == 24,
          f"roles={roles.to_dict()}; external={len(ENVIRONMENTAL)}")
    candidate_groups = dictionary[dictionary.modelling_role == "candidate"].feature_group.value_counts()
    check("features", "The 24 candidates consist of 4 engine, 4 motion, 2 onboard wind, 6 MB and 8 S channels",
          candidate_groups.to_dict() == {
              "engine": 4, "motion": 4, "wind_obs": 2, "env_mb": 6, "env_s": 8,
          },
          candidate_groups.to_dict())

    dq = pd.read_csv(TABLES / "data_quality_summary.csv")
    observed_qids = set(dictionary.index[
        (dictionary.in_monthly_12 == "yes") | (dictionary.in_jan25 == "yes")
    ])
    unobserved_qids = set(dictionary.index) - observed_qids
    numeric_type = "numeric (float64 parsed from CSV text)"
    check("datatypes", "All 36 observed QIDs have audited parsed-float64 type; the PDF-only QID has no invented dtype",
          "data_type" in dictionary.columns
          and len(observed_qids) == 36 and len(unobserved_qids) == 1
          and dictionary.loc[list(observed_qids), "data_type"].eq(numeric_type).all()
          and dictionary.loc[list(unobserved_qids), "data_type"].eq("not_observed").all()
          and dictionary.data_type.str.strip().ne("").all()
          and set(dq.qid) == observed_qids
          and int(dq.n_numeric.sum()) == 42192373
          and int(dq.n_missing.sum()) == 0
          and (dq.n_numeric + dq.n_missing == dq.n_total).all(),
          f"observed={len(observed_qids)}; unobserved={len(unobserved_qids)}; "
          f"audited numeric={int(dq.n_numeric.sum())}; parse failures={int(dq.n_missing.sum())}")
    angular_qids = [qid for qid, (column, _) in CHANNELS.items() if column in ANGLE_COLUMNS]
    check("datatypes", "All angular channels retain numeric dtype; circular meaning is documented separately",
          len(angular_qids) == len(ANGLE_COLUMNS)
          and dictionary.loc[angular_qids, "data_type"].eq(numeric_type).all(),
          f"angular QIDs={len(angular_qids)}; all type={numeric_type}")
    draft = dq[dq.short_name.isin(DRAFT)]
    draft_total = int(draft.n_numeric.sum())
    check("draft", "All 8,226,522 recorded draft values are zero across all 13 files",
          len(draft) == 52 and draft_total == 8226522
          and (draft.n_numeric == draft.n_zero).all()
          and (draft.n_missing == 0).all()
          and (draft["min"] == 0).all() and (draft["max"] == 0).all(),
          f"rows={len(draft)}; numeric={draft_total}; nonzero="
          f"{int((draft.n_numeric-draft.n_zero).sum())}")
    target = pd.read_csv(TABLES / "target_availability.csv").set_index("file")
    check("target", "July and November negative target counts and November minimum match raw audit",
          int(target.loc["7.csv", "n_negative"]) == 28544
          and int(target.loc["11.csv", "n_negative"]) == 656
          and abs(float(target.loc["11.csv", "target_min"]) + 24757.04) < .1,
          f"July={target.loc['7.csv', 'n_negative']}; "
          f"November={target.loc['11.csv', 'n_negative']}; "
          f"November min={target.loc['11.csv', 'target_min']}")
    quality = pd.read_csv(TABLES / "target_quality_month_summary.csv").set_index("month")
    check("target", "Focused July/November scan agrees with monthly target statistics",
          all(int(quality.loc[m, "n_negative_raw"]) == int(target.loc[f"{m}.csv", "n_negative"])
              for m in (7, 11))
          and int(quality.loc[7, "longest_near_contiguous_negative_run_readings"]) > 17000
          and int(quality.loc[7, "n_negative_1min_with_positive_cams_rpm_and_stw_gt_3kn"]) > 6000,
          quality[["n_negative_raw", "longest_near_contiguous_negative_run_readings",
                   "n_negative_1min_with_positive_cams_rpm_and_stw_gt_3kn"]].to_dict("index"))

    coverage = pd.read_csv(TABLES / "overlap_stats_yearwide.csv").set_index("month")
    check("coverage", "September/October count density uses the 15-second calendar denominator",
          abs(float(coverage.loc["Sep", "pct_of_nominal_15sec"]) - 74.9) < .11
          and abs(float(coverage.loc["Oct", "pct_of_nominal_15sec"]) - 49.5) < .11
          and int(coverage.loc["Oct", "n_target_obs"]) == 88304,
          f"Sep={coverage.loc['Sep', 'pct_of_nominal_15sec']}%; "
          f"Oct={coverage.loc['Oct', 'pct_of_nominal_15sec']}%")
    alignment = pd.read_csv(TABLES / "alignment_summary.csv").set_index("sensor")
    overlap = pd.read_csv(TABLES / "overlap_stats_oct2024.csv").set_index("predictor")
    check("alignment", "Pressure is onboard, has no hourly fill, and its target pair count is 22,087",
          alignment.loc["ME_ScavAirPressure_bar", "source_group"] == "onboard"
          and int(alignment.loc["ME_ScavAirPressure_bar", "n_present_after_alignment"]) == 22092
          and int(overlap.loc["ME_ScavAirPressure_bar", "n_coobserved_completed_minutes"]) == 22087,
          alignment.loc["ME_ScavAirPressure_bar"].to_dict())
    provider = overlap[overlap.source_group.isin(["provider_mb", "provider_s"])]
    check("alignment", "All 14 provider channels have target overlap, with repeated raw timestamps disclosed",
          len(provider) == 14
          and (provider.n_coobserved_completed_minutes == 22088).all()
          and (provider.n_distinct_raw_provider_timestamps_used == 369).all()
          and int(overlap.loc["HULL_WaterDepth_m", "n_coobserved_completed_minutes"]) == 0,
          f"provider pair minutes={provider.n_coobserved_completed_minutes.unique().tolist()}; "
          f"distinct source timestamps={provider.n_distinct_raw_provider_timestamps_used.unique().tolist()}; "
          "water depth=0")
    check("alignment", "October target occupies 22,088 of 44,640 completed-minute intervals",
          int(alignment.loc[TARGET, "n_present_after_alignment"]) == 22088
          and int(alignment.loc[TARGET, "n_expected_completed_minutes"]) == 44640
          and alignment.loc[TARGET, "timestamp_semantics"] == "trailing_minute_end",
          alignment.loc[TARGET].to_dict())
    align_fn = runpy.run_path("scripts/06_temporal_alignment.py")["align"]
    synthetic_index = pd.to_datetime(["2024-10-01 00:00:10", "2024-10-01 00:00:30",
                                      "2024-10-01 00:01:10", "2024-10-01 00:01:30"])
    synthetic = pd.DataFrame(np.nan, index=synthetic_index,
                             columns=sorted(COLUMN_TO_SOURCE))
    synthetic.loc[synthetic_index[0], TARGET] = 10
    synthetic.loc[synthetic_index[2], TARGET] = 20
    weather = "WAVE_SigHeight_m_MB"
    synthetic.loc[synthetic_index[1], weather] = 1
    synthetic.loc[synthetic_index[3], weather] = 2
    aligned_synthetic, _ = align_fn(synthetic)
    check("alignment", "Synthetic event-time contract uses no future within-window or provider reading",
          aligned_synthetic.loc["2024-10-01 00:01:00", TARGET] == 10
          and aligned_synthetic.loc["2024-10-01 00:02:00", TARGET] == 20
          and aligned_synthetic.loc["2024-10-01 00:01:00", weather] == 1
          and aligned_synthetic.loc["2024-10-01 00:02:00", weather] == 2
          and pd.isna(aligned_synthetic.loc["2024-10-01 01:02:00", weather]),
          "Synthetic target=10 then 20; weather=1 then 2; >60-min weather age becomes null")

    corr = pd.read_csv(TABLES / "correlation_aligned.csv", index_col=0)
    paired = pd.read_csv(TABLES / "correlation_paired_n.csv", index_col=0)
    expected_cols = {TARGET} | (MODEL_CANDIDATES - ANGLE_COLUMNS)
    check("correlation", "Correlation table excludes leakage, zero draft, sparse depth and circular angles",
          set(corr.columns) == expected_cols
          and set(corr.index) == expected_cols
          and not ((set(corr.columns) & (LEAKAGE | DRAFT | ANGLE_COLUMNS | {"HULL_WaterDepth_m"}))),
          f"columns={len(corr.columns)}; expected={len(expected_cols)}")
    check("correlation", "Pressure/target paired count and Pearson r agree with corrected alignment",
          int(paired.loc[TARGET, "ME_ScavAirPressure_bar"]) == 22087
          and abs(float(corr.loc[TARGET, "ME_ScavAirPressure_bar"]) - .977981) < .0001,
          f"n={paired.loc[TARGET, 'ME_ScavAirPressure_bar']}; "
          f"r={corr.loc[TARGET, 'ME_ScavAirPressure_bar']}")
    independent = pd.read_csv(TABLES / "pivot_oct2024.csv", index_col=0,
                              parse_dates=True,
                              usecols=["ts_parsed", TARGET, "ME_ScavAirPressure_bar"])
    independent = independent.resample("1min").mean()
    independent_n = int(independent.dropna().shape[0])
    independent_r = float(independent[TARGET].corr(independent.ME_ScavAirPressure_bar))
    check("correlation", "Pressure correlation agrees with an independent no-fill pivot calculation",
          independent_n == 22087
          and abs(independent_r - float(corr.loc[TARGET, "ME_ScavAirPressure_bar"])) < 1e-9,
          f"independent n={independent_n}; independent r={independent_r:.9f}")

    poly = pd.read_csv(TABLES / "speed_power_polynomial_diagnostic.csv").iloc[0]
    check("speed-power", "October descriptive cubic falls between 7 and 10 kn; no monotonic claim",
          int(poly.n_paired_minutes) == 22088
          and 350 < float(poly.polynomial_at_7kn_kw - poly.polynomial_at_10kn_kw) < 410,
          f"P7={poly.polynomial_at_7kn_kw:.1f}; P10={poly.polynomial_at_10kn_kw:.1f}")

    noon_dates = []
    invalid = []
    for path in sorted((ROOT / "data/Noon Reports").glob("*.csv")):
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    noon_dates.append(datetime.strptime(row["Date"], "%d/%m/%Y").date())
                except (ValueError, KeyError, TypeError):
                    invalid.append((path.name, row.get("Date")))
    expected_dates = {datetime(2024, 1, 1).date() + timedelta(days=i) for i in range(366)}
    check("noon", "Exactly 366 valid, unique, in-year Noon Report dates",
          len(noon_dates) == 366 and len(set(noon_dates)) == 366
          and set(noon_dates) == expected_dates and len(invalid) == 0,
          f"rows={len(noon_dates)}; unique={len(set(noon_dates))}; "
          f"missing={len(expected_dates-set(noon_dates))}; extra={len(set(noon_dates)-expected_dates)}; "
          f"invalid={len(invalid)}")

    proposal = pd.DataFrame([
        ("train", "2024-01-01", "2024-06-30", "primary; quality rules required"),
        ("quarantine_july", "2024-07-01", "2024-07-31", "target-quality investigation"),
        ("validation", "2024-08-01", "2024-08-31", "chronological model selection"),
        ("coverage_stress", "2024-09-01", "2024-10-31", "reduced observation-count density"),
        ("quarantine_november", "2024-11-01", "2024-11-30", "target-quality investigation"),
        ("test", "2024-12-01", "2024-12-31", "untouched primary holdout"),
    ], columns=["role", "start", "end", "rationale"])
    proposal.to_csv(TABLES / "proposed_split.csv", index=False)
    check("split", "Primary train, validation and test are strictly chronological and disjoint",
          proposal.loc[proposal.role == "train", "end"].iloc[0]
          < proposal.loc[proposal.role == "validation", "start"].iloc[0]
          and proposal.loc[proposal.role == "validation", "end"].iloc[0]
          < proposal.loc[proposal.role == "test", "start"].iloc[0],
          "Train Jan-Jun; validation Aug; test Dec; July/Nov quarantined")

    for name in ("task1_preliminary.md", "task2_preliminary.md", "scientific_validation_report.md"):
        content = (REPORTS / name).read_text(encoding="utf-8")
        check("reports", f"{name} states the canonical split and corrected channel counts",
              all(term in content for term in
                  ["January–June 2024", "August 2024", "December 2024",
                   "14 external", "24 candidate"]),
              "Required split and channel-count phrases checked in report text",
              "Reconcile the report with proposed_split.csv and channel_config.py")
    task2_text = (REPORTS / "task2_preliminary.md").read_text(encoding="utf-8")
    check("datatypes", "Task 2 documents CSV storage, parsed value type, string QIDs and naive January timestamps",
          all(term in task2_text for term in [
              "CSV stores these fields as text",
              "numeric (float64 parsed from CSV text)",
              "not_observed", "categorical key", "timezone-naive",
              "actual timezone is **unconfirmed**", "circular semantics",
          ]),
          "Task 2 raw-schema and dictionary datatype wording checked")

    unresolved("calibration", "Cause and exact boundaries of target anomalies remain unknown",
               "Internal negative readings and independent-channel comparisons flag concerns only",
               "Seek calibration/operations logs; retain sensitivity analysis")
    unresolved("weather", "Provider timestamp issuance, validity and timezone remain unconfirmed",
               "Timestamp text alone does not identify when a weather value became available",
               "Obtain provider metadata before claiming causal inference-time availability")
    unresolved("nowcast", "Engine-signal availability at the operational decision instant is unconfirmed",
               "Current-minute aggregates describe a completed interval",
               "Document deployment timing; construct point-in-time features for Task 3")

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "qa_checklist.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(items[0]))
        writer.writeheader()
        writer.writerows(items)
    counts = pd.Series([item["status"] for item in items]).value_counts().to_dict()
    print("QA", counts, "written to", out)
    for item in items:
        if item["status"] == "FAIL":
            print(item["id"], item["claim"], item["evidence"])
    if counts.get("FAIL", 0):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
