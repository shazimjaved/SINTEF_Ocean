# Scientific validation and correction record
## SINTEF Ocean Real Vessel Data Challenge · Tasks 1 and 2

**Updated:** 25 October 2026.  
**Assessment:** Task 1 and Task 2 are suitable as **preliminary, descriptive client deliverables** with the uncertainties below. No model has been trained. The earlier report's unqualified “approved”, “FAIL 0”, and “all scientific issues resolved” conclusions are withdrawn.

## Independent evidence and concise change log

| Correction | Evidence and current interpretation | Reproducible output |
|---|---|---|
| Channel grouping | An earlier name-fragment rule treated `ME_ScavAirPressure_bar` as external weather and forward-filled it. An explicit QID/source map now classifies it as onboard. Correct October coverage: 22,092 completed minutes; target pairs: 22,087. There are **14 external** channels and **24 candidate** inputs. | `scripts/channel_config.py`, `alignment_summary.csv`, `overlap_stats_oct2024.csv` |
| Time alignment | Onboard values are means of a completed trailing minute labelled by its end. External values use a previous raw timestamp no older than 60 minutes. These are descriptive interval-level values, not a prediction at the minute's start. Provider issuance versus validity timing is unverified. | `scripts/06_temporal_alignment.py`; `fig04c_aligned_coverage.png` |
| Missingness | September and October target counts are 74.9% and 49.5% of a nominal 15-second calendar count. October has 88,304 numeric recorded rows; 76.5% blank cells on a union-timestamp pivot are mostly structural; 22,088/44,640 completed minutes (49.48%) have a target. The count ratios are not verified instrument uptime or a diagnosis of gaps. | `overlap_stats_yearwide.csv`; `fig02c_target_density.png` |
| Co-observation | All 14 provider channels have 22,088 October target-paired minutes, but each has only 643 raw monthly timestamps and **369 distinct timestamps represented in target pairs**. Pressure has 22,087 pairs; engine RPM has 22,086; water depth has zero. Prior statements that every safe onboard input had exactly 22,088 pairs and that 15 weather inputs existed are corrected. | `overlap_stats_oct2024.csv`; `fig11b_target_overlap.png` |
| Correlation | Corrected scalar Pearson values use paired completed minutes, with torquemeter inputs, zero draft, water depth and circular angles excluded. Pressure/target r is +0.978 on 22,087 pairs. Weather minute pairs reuse hourly values; paired count is not effective independent sample size. A minimum-pairs threshold alone cannot establish inferential validity. | `correlation_target_evidence.csv`, `correlation_paired_n.csv`; `fig08c_target_correlation.png` |
| Power versus speed | The October positive-observation cubic falls from 2,955 kW at 7 kn to 2,576 kW at 10 kn. The earlier “transit-only” cubic also fell. Binned observed medians decrease from about 2,997 kW at 7.0–7.5 kn to 2,431 kW at 11.0–11.5 kn. The claim that regime mixing **conclusively** caused the decline is withdrawn. A speed-cubed physical heuristic appears in a separate panel and is not presented as an empirical vessel law. | `speed_power_bins_oct2024.csv`, `speed_power_polynomial_diagnostic.csv`; `fig05c_observed_vs_theory.png` |
| Target quality | A fresh focused scan found July's 28,544 negative raw readings on 14 dates, including three fully negative days and a near-contiguous run of 17,399 readings. November has 656 negative readings on eight dates and a minimum near −24,757 kW. Negative power while independent CAMS RPM and water-relative speed are positive strengthens concern, but does not prove the cause or exact boundaries. July and November are quarantined from the primary proposed split. | `target_quality_daily_jul_nov.csv`, `target_quality_month_summary.csv` |
| Draft and dictionary | All **8,226,522** draft readings across all 13 raw files are zero. Four channels are excluded. The rendered registration table confirms Provider MB/S and m/s for both eastward-current QIDs; two displaced northward-current labels were also corrected. Provider S sea-water temperature is normalized to `C`. The source PDF gives **no unit** for shaft revolutions, so its unit remains blank and documented as unspecified. Water depth has no October target overlap. | `data_dictionary.csv`, `data_quality_summary.csv` |
| Data types | CSV timestamp and QID fields are text, documented separately in Task 2. The full-file quality audit parsed all 42,192,373 observed sensor values as finite binary64 numbers. The dictionary now records the parsed numeric type for 36 observed QIDs and `not_observed` for the PDF-only QID. Angles remain numeric with circular semantics. January 2025 timestamp timezone remains unconfirmed. | `scripts/01_data_dictionary.py`, `data_dictionary.csv`, `task2_preliminary.md` |
| Exact duplicates | A bounded-memory scan of all **42,192,373** raw rows found zero duplicate original `(timestamp, QID)` keys and zero short rows. This resolves the earlier internally answerable “year-wide duplicates unresolved” item. | `scripts/09_duplicate_audit.py`, `duplicate_audit_yearwide.csv` |
| QA logic | Unique IDs, numeric cross-table checks, all-date validation, exact duplicate accounting, and a non-zero process exit on FAIL replace checks based mainly on a file's existence. A PASS now applies only to the written assertion. | `scripts/08_qa_checks.py`, `outputs/reports/qa_checklist.csv` |

No raw sensor or Noon Report file was edited. Prior figures remain on disk for traceability and are marked **superseded** in Task 2 and the README. Current figures have `c` or `b` suffixes as listed in Task 2.

The target QID occurs in all twelve 2024 monthly sensor files and is absent from `Jan25.csv`; January 2025 is not a labelled evaluation set.

The final QA run exited successfully with **33 PASS, 0 FAIL, and 3 UNRESOLVED** entries, all with unique IDs. It includes datatype completeness and Task 2 schema documentation, source-specific dictionary and unit assertions, a synthetic event-time alignment check, an independent no-fill pressure correlation calculation, raw-file count reconciliation, exact duplicate accounting, and strict Noon Report date parsing. `PASS` applies to those assertions only.

**Latest documentation-pass execution evidence (25 October 2026):**

| Command | Exit code | Result |
|---|---:|---|
| `python -B scripts/01_data_dictionary.py` | 0 | Regenerated 37-row dictionary with 36 audited numeric types and one `not_observed` |
| `python -B scripts/08_qa_checks.py` | 0 | 33 PASS, 0 FAIL, 3 UNRESOLVED |

A separate read-only cross-reference check of the three reports, summary tables and six current figure files exited **0** in the prior correction pass. No figure was regenerated in this datatype documentation pass.

## One evaluation proposal

The canonical, chronological proposal in `proposed_split.csv` is **January–June 2024** training, July target-quality quarantine, **August 2024** validation, September–October coverage stress analysis, November target-quality quarantine, and **December 2024** untouched primary test. The proposal resolves the earlier contradiction that simultaneously placed December in training and suggested it as a test month. No test labels have been used to choose model settings because no model has been trained.

## What remains unresolved

1. **Target anomaly mechanism and exact periods.** SINTEF notes miscalibrated torque in parts of the data; the negative readings provide evidence of concern, not a calibration certificate. July and November remain quality-quarantined pending reference or operational records. December's 166 negative labels require predeclared evaluation treatment.
2. **External timestamp semantics.** A past raw timestamp is not proof that a weather value was issued or accessible by that time. Provider timezones and valid-time versus issuance-time meanings require metadata.
3. **Operational feature availability.** Onboard engine signals come from sources distinct from the torquemeter in the registration PDF, but their actual latency and shared data paths have not been verified. A completed-minute reconstruction does not establish an instantaneous or route-planning forecast.
4. **Physical cause of October speed–power decline.** Loading, weather, voyage/time effects and target issues remain hypotheses. October alone cannot resolve them.
5. **Noon Report timing.** All 366 2024 dates are valid and unique. The daily fields' measurement and publication times remain unknown, so a contemporaneous same-day join is not established.

## Client-readiness boundary

Task 1 and Task 2 can be shared as **preliminary problem-definition and data-understanding results**, provided the reports, current figures and this correction record travel together. They do not establish model accuracy, fuel savings, causal weather effects, a validated speed–power law, or production readiness. The QA checklist reports computational checks and unresolved questions separately; a zero-FAIL result is not a claim that these scientific boundaries have disappeared.

## Preliminary client handover set

- Reports: `task1_preliminary.md`, `task2_preliminary.md`, `scientific_validation_report.md`, and `qa_checklist.csv` in `outputs/reports/`.
- Dictionary and split: `data_dictionary.csv` and `proposed_split.csv` in `outputs/tables/`.
- Current figures: `fig02c_target_density.png`, `fig04c_aligned_coverage.png`, `fig05c_observed_vs_theory.png`, `fig08c_target_correlation.png`, `fig10b_daily_counts.png`, and `fig11b_target_overlap.png` in `outputs/figures/`.

Supporting summary tables cited by Task 2 remain in `outputs/tables/` for audit. Raw sensor and Noon Report CSVs, the donor-identifying source material, and superseded figures are **not** part of this handover set.
