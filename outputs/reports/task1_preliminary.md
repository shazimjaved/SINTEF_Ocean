# Task 1 — Problem definition and business understanding
## SINTEF Ocean Real Vessel Data Challenge · NTNU TDT4259

**Status:** Client-ready preliminary problem definition; no predictive model has been trained or evaluated.  
**Updated:** 25 October 2026.  
**Data handling:** The donor vessel and shipowner are not identified here. Raw data remain local.

## 1. Decision and scope

The proposed technical question is whether independently sourced operational and environmental measurements can estimate **shaft mechanical power (kW)** when a trusted torquemeter output is unavailable, or support a plausibility check of that output. An estimate might support onboard performance monitoring. Any fuel or routing benefit requires a separate business evaluation after predictive accuracy and operational availability are established.

This preliminary task is an **interval-end reconstruction** of power for a completed one-minute interval. At an interval end called time t, onboard features may summarize readings from the preceding minute through t. The label is the torquemeter's mean power over that same completed interval. This is not a prediction made at the *start* of that minute. A truly instantaneous or future route-planning use requires a separately specified prediction horizon and only inputs known before that decision; the present analysis does not validate either use.

Provider weather values are attached from the latest raw timestamp at or before (t), no more than 60 minutes old. **The dataset does not establish whether that timestamp is an issuance time or a weather-valid time.** Operational use of those features is conditional on provider metadata confirming availability by (t). Engine transducer/CAMS source labels are distinct from the torquemeter, but their operational latency and independence of the data path also require confirmation.

## 2. Target and candidate inputs

**Target QID:** `2::0::11::0_1::1::0::3::0_14::0::1::0_8`, Vessel Propeller Shaft Mechanical Power, kW. It appears in all twelve 2024 monthly sensor files and is absent from `Jan25.csv`; January 2025 cannot be a labelled test set.

Of the **36 observed 2024 channels**, the preliminary classification is:

| Role | Channels | Treatment |
|---|---:|---|
| Target | 1 | Prediction label; quality-screened before modelling |
| Same torquemeter or close proxy | 6 | Exclude from inputs: torque, energy, thrust, shaft revolutions, shaft RPM, and torquemeter-sourced fuel mass flow |
| Constant-zero draft | 4 | Exclude; all 8,226,522 recorded values across 2024 and Jan 2025 are zero |
| Water depth | 1 | Exclude from the primary proposal; zero paired October completed minutes with target; revisit for other periods only with evidence |
| **Candidate inputs** | **24** | Four independent-source engine channels, four motion channels, two onboard relative-wind channels, and **14 external** Provider MB/S channels |

The **24 candidate** inputs are not proven leakage-free operational features. Engine state at the end of the interval may be an informative proxy for power, but it cannot be assumed available in a route plan. Noon Report displacement is a possible loading proxy; a same-day daily value must not be copied into earlier minutes until its measurement and issuance time are known. A lagged value is safer if availability can be established.

## 3. Scientific constraints

- **Target quality:** July has 28,544 negative readings, including three full days of negative power and a near-contiguous 17,399-reading negative run. November has 656 negative readings and a minimum near −24,757 kW. The SINTEF material warns of torque miscalibration in parts of the dataset. These observations strongly motivate quality quarantine, but they do **not** prove the fault mechanism or exact calibration boundaries. Negative readings remain in the raw data.
- **Missingness:** The 2024 long-format target rows have numeric values, but that says nothing about calendar coverage. September and October have **74.9%** and **49.5%**, respectively, of the calendar count at a nominal 15-second rate. October has 88,304 target readings, occupying 22,088 of 44,640 completed-minute intervals across 16 active dates. The count ratio does not by itself identify the cause of absent observations.
- **Weather repetition:** In October each provider channel has 643 raw hourly readings; the 22,088 target-paired completed minutes reuse values from only **369 distinct provider timestamps**. These are not 22,088 independent weather observations.
- **Direction variables:** Heading and wind/wave angles are circular. Arithmetic averages and plain Pearson correlations across a 0°/360° boundary can mislead; they are omitted from the scalar correlation figure pending appropriate treatment.
- **Representativeness:** A single vessel, changing loading and operating conditions, serial dependence, and uneven coverage constrain generalization. October's observed power–speed association cannot be treated as the vessel's resistance law.

## 4. One chronological evaluation proposal

This proposal is fixed for Task 3 planning in `outputs/tables/proposed_split.csv`; no split or model has yet been executed.

| Role | Period | Reason |
|---|---|---|
| Primary training | **January–June 2024** | Earlier labelled period; apply documented quality rules |
| Target-quality quarantine | July 2024 | Sustained negative-power episode; investigate separately |
| Validation | **August 2024** | Later period for method and parameter decisions |
| Coverage stress analysis | September–October 2024 | Reduced target observation-count density; report separately |
| Target-quality quarantine | November 2024 | Extreme negative outlier and additional suspect readings |
| Untouched primary test | **December 2024** | Latest 2024 labelled month; use only after choices are frozen |

The split is chronological and disjoint. The December test should be reported both on all observed labels and, if justified, under **predeclared** quality criteria established without inspecting test errors. Its 166 negative readings must be disclosed. July and November should not enter primary fitting or headline test metrics without a documented, sensor-supported quality decision. Their quarantined periods can be used for fault and robustness analysis.

## 5. Evaluation and success criteria

Task 3 should compare a training-mean baseline, a speed-based physical heuristic fitted on training data, and persistence **only where the preceding trusted target value would actually be available**. Report MAE and RMSE in kW and R² as context, with sample counts and time-block uncertainty. Evaluate by month, speed/loading proxy, and anomaly/coverage stratum where data permit. Beating baselines on the untouched test is a minimum technical criterion; the acceptable error for an operational decision must be set with stakeholders rather than invented here.

No model accuracy, fuel saving, or route-optimization benefit is claimed in this preliminary deliverable.

## 6. Evidence and open decisions

The sensor inventory and roles are in `outputs/tables/data_dictionary.csv`; corrected alignment, overlap, and correlation evidence are in `outputs/tables/alignment_summary.csv`, `overlap_stats_oct2024.csv`, and `correlation_target_evidence.csv`. July/November details are in `target_quality_daily_jul_nov.csv` and `target_quality_month_summary.csv`. The independent exact duplicate audit is in `duplicate_audit_yearwide.csv`; the QA gate is `outputs/reports/qa_checklist.csv`.

Before model training: confirm weather issuance/validity semantics and engine-signal latency, define quality thresholds without test tuning, decide whether lagged Noon Report fields are available, and retain the time-blocked evaluation design.
