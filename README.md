# SINTEF Ocean Real Vessel Data Challenge

This project contains preliminary Task 1 (problem definition) and Task 2 (data understanding) findings and an executed Task 3 modelling study for NTNU TDT4259. The current Task 3 academic report, separate technical appendix and reproducibility instructions are in `outputs/task3/reports/task3_academic_report.pdf`, `outputs/task3/reports/task3_technical_appendix.md` and `outputs/task3/README.md`. The donor vessel and shipowner must not be identified or inferred from these materials. Never publish or upload raw sensor or Noon Report data.

## Inputs and outputs

- `data/raw/`: twelve 2024 monthly long-format CSVs and `Jan25.csv`; confidential, never rewritten by the scripts.
- `data/Noon Reports/`: twelve confidential daily CSVs; never rewritten.
- `docs/`: supplied challenge and metric-registration PDFs.
- `scripts/`: schema, dictionary, quality, pivot, descriptive alignment, figure, target-window, duplicate and QA scripts.
- `outputs/tables/`: derived Task 1/2 summary tables. `outputs/figures/`: derived Task 1/2 figures. `outputs/reports/`: preliminary deliverables and QA checklist.
- `outputs/task3/`: compressed minute tables, trained model, evaluation tables and plots, Task 3 QA and technical report. Follow its own `README.md` for the frozen holdout protocol.

The preliminary Task 1/2 handover reports are `outputs/reports/task1_preliminary.md`, `task2_preliminary.md`, and `scientific_validation_report.md`. The latter contains the concise change log and unresolved scientific questions. Task 3 does not alter those completed reports.

## Reproduce preliminary Tasks 1/2 on an 8 GB CPU-only laptop

Run from the project root using Python 3.11+ and `pip install -r requirements.txt`. Run the substantial raw-file passes **sequentially** to limit peak memory; they stream one file at a time. The October pivot is the largest in-memory intermediate. `python -B` avoids writing bytecode caches.

```powershell
python -B scripts/00_schema_audit.py
python -B scripts/02_quality_audit.py
python -B scripts/01_data_dictionary.py
python -B scripts/03_pivot_representative.py
python -B scripts/04_eda_plots.py
python -B scripts/05_noon_report_audit.py
python -B scripts/09_duplicate_audit.py
python -B scripts/10_target_quality_windows.py
python -B scripts/06_temporal_alignment.py
python -B scripts/06b_corr_and_figures.py
python -B scripts/07_regime_analysis.py
python -B scripts/08_qa_checks.py
```

Scripts 00–05 produce the initial inventory, quality summaries, and October pivot. Run script 02 before 01: the dictionary's `data_type` column is based on the full-file numeric audit rather than inferred from a QID name. Scripts 09–10 independently audit exact duplicate keys and July/November target windows. Script 06 uses the explicit QID/source mapping in `channel_config.py` and labels onboard averages at the **end** of a completed trailing minute; its weather lookup uses prior raw timestamps no more than 60 minutes old. Script 06b makes the corrected coverage/overlap/correlation figures, and script 07 makes the observed versus theoretical speed–power figure. Script 08 writes `qa_checklist.csv` and exits non-zero if a numeric or consistency check fails. It also writes `proposed_split.csv`.

The dictionary generator includes corrections checked against the rendered Metrics registration table: both eastward-current provider sources and m/s units, Provider S sea-water temperature unit `C`, and an intentionally unspecified shaft-revolutions unit. To regenerate only the revised target-density chart, run `python -B scripts/06b_corr_and_figures.py --figure 02c`.

If the initial 00–05 outputs already exist and raw data have not changed, the affected analysis can be refreshed by running 01, 09, 10, 06, 06b, 07 and 08 in that order. All generated artifacts are inside `outputs/`; no script modifies either input directory.

## Current interpretation

- The 2024 files contain 41,079,968 rows and 36 observed QIDs; all 13 files contain 42,192,373 rows. January 2025 has no labelled power target.
- Of 36 observed 2024 channels, there are one target, six excluded torquemeter channels, four excluded constant-zero draft channels, one water-depth channel excluded from the primary October analysis, and **24 candidate** channels including **14 external** provider channels.
- October has 22,088 target-paired completed minutes. Provider values in those pairs come from only 369 distinct raw timestamps per channel; paired minutes are not independent weather observations.
- The preliminary chronological proposal is **January–June 2024** training, **August 2024** validation, and **December 2024** untouched test. July and November are quality-quarantined; September–October are coverage stress periods. Task 3 executed this split and evaluated December once after freezing the selected approach.
- The provider timestamp's issuance/validity meaning and the torquemeter anomaly mechanism are unresolved. A completed-minute reconstruction is not an instantaneous or future prediction.

## Figure status

Use `fig02c_target_density.png`, `fig04c_aligned_coverage.png`, `fig05c_observed_vs_theory.png`, `fig08c_target_correlation.png`, `fig10b_daily_counts.png`, and `fig11b_target_overlap.png` for the current preliminary reports. Earlier `fig02`/`fig02b`, `fig04`/`fig04b`, `fig05`/`fig05b`, and `fig08`/`fig08b` remain in `outputs/figures/` as **superseded audit artifacts**. Other older figures are legacy context and are not part of the current client evidence set.

`outputs/tables/regime_summary.csv` is also superseded: its categories used target power and did not explain the observed speed–power decline. The current empirical evidence is `speed_power_bins_oct2024.csv` and `speed_power_polynomial_diagnostic.csv`.
