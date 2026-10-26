# Task 3 V3: internal target-reliability and cross-period investigation

This is internal experimental evidence, not a client report. V1/V2 artifacts and raw data remain unchanged. Torquemeter readings below are **diagnostic only**; they are excluded from every ranked model. December is absent from all V3 matching, clustering and model experiments.

## 1. Recorded zero-power states

The year-wide chunked raw-QID audit independently reproduced every V1 target minute count and mean. Of 366,627 forward minutes with a recorded target, **40,200 have recorded zero power**. **38,990** of these also meet the diagnostic active-engine condition (CAMS RPM>50, fuel load>20%, scavenging pressure>0.5 bar), or 10.6% of forward target minutes. In **all 38,990**, torquemeter shaft RPM, torque and thrust are also zero. The torquemeter revolution and energy counters are unchanged from the previous minute in **38,985**; three exceptions are zero-run onsets, and two are downward counter steps 19–20 minutes into the August run. The exceptions are retained in the CSV, not hidden.

Raw 15-second transitions at the June 10, August 27 and November 11 onsets switch power, torque, shaft RPM and thrust to zero **on the same sample**. Ten-minute median CAMS RPM changes at those onsets are +0.03%, −0.21% and +0.12%; fuel-load changes are −0.21%, −0.98% and −0.43%, while vessel speed stays positive. A November 12 recovery switches the four mechanical channels positive on the same sample. The September 4 run start, and the June/August/September sampled run ends, are **speed-threshold boundaries while power was already zero**; they are not sensor onset or recovery events. Representative raw readings and plots are in `zero_states/`.

**Supported:** zero is a coordinated state across the mechanical torquemeter channels, visible in the raw source and not introduced by one-minute aggregation. The independent engine and speed channels continue through several sampled onsets. The cumulative counter steps complicate any claim of perfectly frozen instrumentation. **Unresolved:** whether the torquemeter package reported a fault/default zero, the shaft was genuinely disengaged or stopped while the engine ran, or another drivetrain/propulsion configuration applied. The torquemeter channels share an instrument and are not independent confirmation of physical shaft state. No zero has been relabelled as faulty.

## 2. Power scale and relationship shift

For positive-power minutes, the median numerical factor `power_kW / (torque_numeric × shaft_RPM)` is **0.10472 in every 2024 month**. This agrees with `2π/60` if the torque numbers represent kN·m, and is **1,000×** the conversion implied by the registration PDF's literal **N·m** unit. In 474 positive sampled raw triplets, the kN·m-formula mean absolute discrepancy is 6.61 kW. This is a verified numerical unit/scaling inconsistency, not evidence that the power channel changed scale between months. The source dictionary has not been changed; the exact export scaling needs confirmation from instrumentation metadata.

Earlier-only four-feature matching (STW, CAMS RPM, fuel load, scavenging pressure; five training neighbors; all five within 0.5 training IQR units) separates distribution and relationship differences on the **positive-target headline**:

| Validation | Matched / complete | Feature-composition component | Conditional target component |
|---|---:|---:|---:|
| April | 5,525 / 36,275 (15.2%) | −295 kW | +26 kW |
| May | 16,402 / 17,851 (91.9%) | −469 kW | +104 kW |
| June | 12,067 / 12,084 (99.9%) | +717 kW | −91 kW |
| August | 25,736 / 35,086 (73.4%) | −446 kW | **−991 kW** |

These components describe **matched common support only**; April has low overlap. Train-defined eight-cluster engine regimes also show lower August target means in each populated cluster, so a simple change in cluster frequency does not explain the shift. At the same August matched conditions, diagnostic torquemeter torque is **110.7 numeric units lower** (validation/reference ratio **0.796**), while shaft RPM is only **0.31 RPM lower** (ratio **0.996**). The power difference is therefore expressed mainly in the torque channel, not a changed power-conversion factor or shaft/engine RPM ratio. This remains compatible with real load differences, torque-channel calibration/scaling changes, or missing operating-state variables; the available signals cannot distinguish them.

## 3. Label-free chronological model tests

V3 tested onboard ratios and trailing 15/60-minute statistics (current completed minute and earlier only) with training-fold-only imputation/scaling. Folds were Jan–Mar→Apr, Jan–Apr→May, Jan–May→Jun, Jan–Jun→Aug. July/November were quarantined; December was not opened for model work. The table below is the best new V3 candidate by equal-fold mean headline MAE, **extended-onboard Ridge with derived ratios, recent 90 days**. `R` is Pearson correlation; R² is separate. Complete candidate and baseline results are in `models/v3_development_with_v2_baselines.csv` and the scope-separated plot is `models/v3_label_free_fold_metrics.png`.

| Fold | Scope | n | MAE kW | RMSE kW | R | R² | Bias kW (actual−predicted) |
|---|---|---:|---:|---:|---:|---:|---:|
| Apr | Positive headline | 42,465 | 138.6 | 167.0 | .994 | .970 | +128.6 |
| Apr | Broader forward | 42,468 | 138.7 | 168.4 | .994 | .969 | +128.8 |
| May | Positive headline | 17,851 | 122.7 | 169.7 | .991 | .979 | −58.8 |
| May | Broader forward | 17,903 | 126.0 | 193.1 | .988 | .974 | −57.7 |
| Jun | Positive headline | 12,084 | 108.6 | 124.5 | .990 | .925 | −106.4 |
| Jun | Broader forward | 30,112 | 3,299.5 | 4,325.4 | .254 | −1.263 | −3,293.4 |
| Aug | Positive headline | 35,086 | 1,046.9 | 1,051.8 | .992 | −1.844 | −1,046.9 |
| Aug | Broader forward | 41,205 | 1,525.0 | 1,921.8 | .580 | −.811 | −1,523.6 |

The derived features improve April/May and the equal-fold mean headline MAE (354.2 versus V2 Ridge's 373.9 kW), but **worsen August** (1,046.9 versus 1,032.4 kW). Trailing-history Ridge and HGB also leave August R² negative. No tested label-free feature set resolves the temporal shift or the broad-scope zero state. The positive-target headline uses a target-dependent retrospective eligibility rule and cannot be assumed observable at inference.

## Required external evidence before a causal diagnosis

1. Torquemeter status/alarm and communication logs, calibration certificates, export scaling, and the intended torque unit; specifically explain the apparent 1,000× N·m factor and August counter steps.
2. Gearbox, clutch, power-take-off and propulsion-lineup/event logs for the June, August–September and November zero episodes; an independent shaft tachometer or torque/power measurement if available.
3. Independent fuel-flow/engine-load measurements and trustworthy loading/draft, displacement, trim and operating-mode records with timestamps. The four current draft channels are constant zero and cannot supply this context.
4. Timestamp issuance/validity and availability records for provider weather if such features are reconsidered.

No V3 model has been promoted or evaluated on December. The current evidence supports further engineering investigation, not a calibration correction, relabelling rule, or deployment claim.

## Reproduction

Run `scripts/task3_v3/01_zero_transition_raw.py`, `02_yearwide_torquemeter_audit.py`, `03_fold_shift_decomposition.py`, `04_label_free_temporal_models.py`, `05_torquemeter_identity.py`, `06_transition_classification.py`, `07_plot_models.py`, `09_matched_torque_shift.py`, then `08_qa.py` from the project root. The model experiment script refuses to overwrite its existing output; use a new experiment name for a new fit. The final V3 QA run exits 0 with **17 PASS, 0 FAIL**. Its checks include V1 frozen-artifact hashes, raw target-to-minute reconciliation (during processing), synchronized mechanical transitions, fold chronology, trailing-window direction, scope counts and metric identities. No raw record or V1/V2 frozen artifact was written.
