# Task 2 — Data understanding and background
## SINTEF Ocean Real Vessel Data Challenge · NTNU TDT4259

**Status:** Client-ready preliminary data understanding; descriptive analysis only.  
**Updated:** 25 October 2026.  
**Confidentiality:** This report does not identify the donor vessel or shipowner.

## 1. Inventory and provenance

The twelve 2024 long-format sensor files contain **41,079,968 rows**; `Jan25.csv` adds **1,112,405**, for **42,192,373 rows**. A separate exact streaming audit found **zero duplicate (timestamp, QID) keys and zero short rows** in all 13 files. The registration PDF contains 37 QIDs; 36 occur in the 2024 files and 26 in January 2025. The unobserved registered QID is an engine turbocharger RPM indicator channel. January 2025 lacks all torquemeter channels, including the power target, so it is not a labelled evaluation set.

The 2024 files have three headerless CSV fields; `Jan25.csv` has a header and four fields. **CSV stores these fields as text.** Their parsed types and timestamp meanings are:

| Field | 2024 files | January 2025 file |
|---|---|---|
| Timestamp | ISO 8601 text with a `Z` suffix and millisecond precision; parse as a UTC-aware datetime | Day-first `DD/MM/YYYY HH:MM:SS` text without a timezone; parse as a timezone-naive datetime. Its actual timezone is **unconfirmed**, so UTC must not be assumed |
| QID | Hierarchical identifier stored as a string; treat as a categorical key, never as a numeric measurement | Same string identifier type |
| Sensor value | Numeric text parsed to Python `float`/binary64 | Numeric text parsed to Python `float`/binary64 for the 26 observed QIDs |
| `Number of Records` | Absent | Fourth, integer-formatted text field; its aggregation meaning is unconfirmed |

The full-file quality audit parsed all **42,192,373 observed sensor values** as finite numbers with zero parse failures. The dictionary's `data_type` column records `numeric (float64 parsed from CSV text)` for each observed sensor QID. The one PDF-registered QID never observed in the CSVs is marked `not_observed`; no measured dtype is inferred for it. Angles are numeric values with **circular semantics**, handled separately from their storage type. The 2024 source rows are not internally sorted by time. All summaries preserve raw files without modification. File-by-file counts and QID presence are in `outputs/tables/data_inventory.csv`, `qid_per_file.csv`, and `duplicate_audit_yearwide.csv`.

## 2. Sampling, alignment and what “missing” means

Three denominators answer different questions for October shaft power:

| Denominator | Result | Interpretation |
|---|---:|---|
| Recorded target rows | 88,304 numeric / 88,304 recorded | No null numeric values *within recorded target rows* |
| Union of all raw sensor timestamps | 88,304 / 376,474 present, about 76.5% blank | Mostly structural blank cells from different sensor timestamps and rates; not a calendar coverage measure |
| Completed one-minute intervals | 22,088 / 44,640, **49.48% covered** | Calendar coverage of the interval-level target in October |

For descriptive alignment, each onboard value is the mean of readings in a **trailing one-minute interval labelled by its end**. The October grid runs from 1 October 00:01 through 1 November 00:00, representing all 44,640 October minutes. An interval value contains no reading later than its label, but it describes a completed interval; it is not an instantaneous reading or a prediction at the minute's start. Each external channel uses its latest raw timestamp no later than that interval end, with a maximum age of 60 minutes. **Provider issue time, weather-valid time, and timezone semantics are not confirmed**, so the resulting external features are descriptive until provider metadata establishes inference-time availability.

Grouping uses an explicit QID/source map. The scavenging-air-pressure transducer is onboard; an earlier substring rule incorrectly gave it an hourly weather fill. Corrected October pressure coverage is **22,092** completed minutes, with **22,087** paired with target. The target covers 22,088 completed minutes. Each of the **14 external** Provider MB/S channels has 643 raw October readings, 38,601 aligned minute values (86.47% of the calendar grid), and 22,088 paired target minutes. Those pairs draw on only **369 distinct provider timestamps** per channel, so they are not 22,088 independent weather observations. Echosounder water depth has 61 completed minutes, **zero** paired with the October target.

The annual target-count ratio uses a *nominal* 15-second calendar denominator. It measures observation-count density, not the fraction of time the instrument was operational, and it cannot establish why readings are absent:

| Month | Recorded target readings | Nominal count density | Negative readings |
|---|---:|---:|---:|
| Jan | 166,699 | 93.4% | 115 |
| Feb | 166,389 | 99.6% | 111 |
| Mar | 149,512 | 83.7% | 30 |
| Apr | 171,160 | 99.1% | 20 |
| May | 170,498 | 95.5% | 189 |
| Jun | 162,159 | 93.8% | 0 |
| Jul | 178,007 | 99.7% | **28,544** |
| Aug | 178,534 | 100.0% | 495 |
| Sep | 129,509 | **74.9%** | 138 |
| Oct | 88,304 | **49.5%** | 37 |
| Nov | 170,683 | 98.8% | 656 |
| Dec | 176,579 | 98.9% | 166 |

October target readings occur on 16 of 31 calendar dates. The lower September and October densities warrant coverage-stratified analysis; an outage or operational explanation cannot be inferred solely from the ratios.

## 3. Channel quality and candidate inputs

Of the 36 observed 2024 QIDs, **24 candidate** inputs remain after excluding the power target (1), same-torquemeter measurements and close proxy (6), constant-zero draft channels (4), and water depth from the primary October-overlap proposal (1). The candidates comprise four independent-source engine, four motion, two onboard relative-wind, and **14 external** channels. The four draft channels have **8,226,522 recorded values across all 13 files, all exactly 0.0 m**. This verifies unusable readings, not the installation or export cause. Water depth may be reassessed outside October if overlap and meaning are demonstrated.

The registration PDF extraction displaced the quantity labels for two northward sea-water-current QIDs and merged the eastward-current quantity text with its Provider MB/S source cells. The corrected `data_dictionary.csv` names both eastward channels, assigns their sources to Provider MB and Provider S with m/s units, and retains provenance notes. Provider S sea-water temperature uses normalized unit `C`. The PDF leaves the shaft-revolutions unit blank; the dictionary therefore records it as **unspecified**, without inferring a unit. These corrections were checked against the rendered PDF table. Angular channels (heading, relative wind angle, true wind angle, wave angle) require circular treatment; they remain candidate inputs but are excluded from the plain Pearson figure.

**Target-quality concern:** July has 28,544 negative target readings across 14 dates. Every target reading on July 11, 12 and 15 is negative; the longest near-contiguous negative run is 17,399 readings. At the one-minute level, **6,948** negative-power intervals also have positive CAMS engine RPM and speed through water above 3 kn. November has 656 negative raw readings across eight dates, minimum about **−24,757 kW**, and 93 such negative-power intervals with positive CAMS RPM and speed above 3 kn. These observations justify quality quarantine. They do **not** by themselves identify calibration, reversal, sign convention, or exact fault boundaries. No negative value has been silently removed. June has no negative target readings; clipping is only a possibility, not a finding.

## 4. Descriptive October relationships

The corrected scalar Pearson analysis is on completed-minute pairs and excludes torquemeter inputs, constant draft, sparse water depth and angular channels. Selected correlations with shaft power are:

| Predictor | Pearson r | Paired completed minutes |
|---|---:|---:|
| Scavenging air pressure | +0.978 | 22,087 |
| Turbocharger RPM, transducer | +0.950 | 22,087 |
| Fuel load % | +0.920 | 22,087 |
| Engine RPM, CAMS | +0.880 | 22,086 |
| Speed over ground | +0.638 | 22,088 |
| Speed through water | +0.628 | 22,088 |
| MB significant wave height | +0.256 | 22,088; **369 distinct raw weather timestamps** |

These are descriptive associations within an unusually narrow October operating envelope. Serial dependence, repeated weather values, loading, and operational regime prevent interpreting paired-minute counts as independent samples or correlations as causal effects. The full values and paired counts are in `correlation_target_evidence.csv`, `correlation_aligned.csv`, and `correlation_paired_n.csv`.

The observed October speed–power relation is **not consistently increasing**. Among nonnegative-speed and nonnegative-power completed minutes, the median falls from about **2,997 kW at 7.0–7.5 kn** to **2,564 kW at 10.0–10.5 kn** and **2,431 kW at 11.0–11.5 kn**. The earlier unconstrained all-positive cubic likewise falls from about 2,955 kW at 7 kn to 2,576 kW at 10 kn. Its previously labelled “transit-only” version also fell; regime mixing has **not** been established as the cause. The illustrative physical speed-cubed curve is shown separately and is not fitted as an empirical vessel law. Loading, environmental conditions, time/voyage effects, and possible sensor issues remain hypotheses for further study. See `speed_power_bins_oct2024.csv` and `fig05c_observed_vs_theory.png`.

## 5. Noon Reports and evaluation implications

The twelve Noon Report files contain **366 valid unique dates**, covering every date in leap year 2024. Their daily resolution is much coarser than sensor readings. The June file has missing fuel type and propulsion consumption, and 18 extreme slip entries were flagged across the year (including −60% and +50%). Same-day displacement may have been recorded or issued after some sensor minutes; its availability must be resolved before joining it as a feature. It may be used as a lagged loading proxy if timing is documented.

The single chronological Task 3 proposal is **January–June 2024** primary training, July target-quality quarantine, **August 2024** validation, September–October coverage stress analysis, November target-quality quarantine, and **December 2024** untouched primary test. December's 166 negative readings must be disclosed and handled under criteria fixed before test evaluation. No model has been trained, and no predictive accuracy or business value is asserted here.

## 6. Figures, limits and reproducibility

Current figures are `fig02c_target_density.png`, `fig04c_aligned_coverage.png`, `fig05c_observed_vs_theory.png`, `fig08c_target_correlation.png`, `fig10b_daily_counts.png`, and `fig11b_target_overlap.png`. Earlier `fig02`, `fig02b`, `fig04`, `fig04b`, `fig05`, `fig05b`, `fig08`, and `fig08b` files remain as **superseded audit artifacts** and should not be used in a client presentation. Other older figures are legacy context outside this deliverable's evidence set. The exact duplicate audit, quality-window tables, split proposal and QA checklist are in `outputs/tables/` and `outputs/reports/`.

The old `regime_summary.csv` is likewise superseded because it uses target power to define categories and does not establish the cause of the speed–power decline.

Remaining external questions include torquemeter calibration/operation logs, provider issue/valid-time metadata, and operational timing of engine and Noon Report fields. The QA checklist tests reproducible numeric assertions; it does not convert these uncertainties into verified facts.
