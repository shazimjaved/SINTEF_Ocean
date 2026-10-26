# Task 3 V4: internal engineering-aware experiments

This is an internal modelling note. No V1/V2/V3 artifact or raw record was changed. The V4 model experiment used only chronological development folds Jan–Mar→Apr, Jan–Apr→May, Jan–May→Jun and Jan–Jun→Aug. July/November remained quarantined; December was not used for fitting, ranking or calibration.

## Identifiability of recorded shaft-zero state

The retrospective diagnostic state is recorded zero power with STW≥3 kn, CAMS RPM>50, fuel load>20% and scavenging pressure>0.5 bar. It is an **output label only**, never a predictor, and is not proven to equal physical shaft disengagement or measurement failure. Training Jan–Jun contained 175,558 active-engine examples, including 17,268 recorded-zero minutes. August validation contained 41,022, including 5,998 zeros.

| Independent onboard feature set | August ROC AUC | Average precision | Recall at fixed 0.5 threshold |
|---|---:|---:|---:|
| Restricted navigation/wind | .645 | .176 | 0 |
| Extended engine | .493 | .137 | 0 |
| Extended engine + trailing history | .645 | .236 | 0 |

August zero prevalence was .146. For the late-August raw onset, the engine-history classifier's median zero probability was .0034 in the preceding ten minutes and .0045 in the first ten zero minutes. Within August, **45.2%** of zero-state minutes had five positive-power analogs within a fixed 0.25 Jan–Jun IQR distance on speed, engine RPM, fuel load and pressure (57.1% within 0.5). These are descriptive overlaps, not a mathematical impossibility proof. The only training zero episodes occur late in June, which limits generalization to another month. The available independent features do not provide a reliable tested state detector.

## Noon loading context and temporal eligibility

All twelve Noon CSVs contain 366 unique 2024 dates but **no measurement or issuance time column**. Same-day and prior-day Noon values were therefore excluded from ranked model inputs; even a prior-day join lacks a verified availability deadline. Retrospectively, August displacement is 89,145 on all 31 dates, so it cannot identify the late-August zero onset within that month. Its high level may indicate a different loading context, but date-only reports cannot establish which minute had access to the value, and no causal loading explanation is supported. Daily loading summaries and eligibility decisions are in `noon/`.

## Label-free development models

Fifteen fixed candidates covered Ridge, HGB, XGBoost, LightGBM and CatBoost, restricted onboard versus extended engine versus derived/trailing onboard inputs, and three broad-label training ablations. Each fit used earlier permitted months only, at most two boosting threads, and training-only imputation/scaling when needed. Predictions and exact MAE, RMSE, R², Pearson r, bias and n for **every candidate, fold and evaluation scope** are in `models/v4_boosting_development.csv` and `models/predictions/`. `models/v4_scope_stability.csv` and the family/ablation PNGs summarize them without changing the results.

On the same extended onboard inputs with positive-target training, August headline MAE/R² were: Ridge **1,032/−1.761**, HGB **1,096/−2.108**, XGBoost **1,079/−2.020**, LightGBM **1,099/−2.125**, CatBoost **1,073/−2.001** kW. No stronger family resolved the cross-period offset. Derived and trailing features did not yield positive August headline R². Broad-label training did not resolve it either: the best broad-trained XGBoost candidate had August headline MAE **897 kW**, R² **−1.885**, Pearson r **.63**, and broader-forward MAE **1,384 kW**, R² **−.926**. Its smaller mean bias does not indicate accurate minute predictions.

The restricted onboard HGB had a lower August headline MAE (**755 kW**) and positive August broader-forward R² (**.385**), but April/May headline MAEs were **795/812 kW** and June broader-forward MAE was **3,305 kW** with R² **−1.155**. It is not consistently accurate. **All 15 candidates have negative August headline R²; all 15 have negative June broader-forward R².** The headline is a target-dependent retrospective subset, so broad-scope failure cannot be hidden by it.

For a fixed reference, the label-free extended-onboard Ridge (recent 90 days) scored:

| Fold | Scope | n | MAE kW | RMSE kW | R² | Pearson r | Bias kW (actual−predicted) |
|---|---|---:|---:|---:|---:|---:|---:|
| Apr | Positive headline | 42,465 | 214.7 | 240.2 | .937 | .993 | +210.2 |
| Apr | Broader forward | 42,468 | 214.8 | 240.5 | .937 | .993 | +210.3 |
| May | Positive headline | 17,851 | 140.7 | 187.0 | .974 | .989 | −65.8 |
| May | Broader forward | 17,903 | 143.9 | 202.2 | .971 | .987 | −63.5 |
| Jun | Positive headline | 12,084 | 107.8 | 123.1 | .927 | .990 | −105.5 |
| Jun | Broader forward | 30,112 | 3,307.7 | 4,333.1 | −1.272 | .250 | −3,299.1 |
| Aug | Positive headline | 35,086 | 1,032.4 | 1,036.3 | −1.761 | .992 | −1,032.4 |
| Aug | Broader forward | 41,205 | 1,512.9 | 1,914.0 | −.796 | .575 | −1,510.0 |

The exact unrounded values are in the CSV. No label-free V4 model was promoted.

## Separate conditional label-assisted scenario

This scenario assumes trustworthy shaft-power labels become available with **one full UTC day of delay**. At each day start, it adds the median residual from eligible positive-power readings in the three-day window ending 24 hours earlier; it never uses same-day or future labels. It reads saved V4 Ridge predictions and does not refit the base models. This is **different information** from label-free estimation and is not in the ranked comparison.

For extended-onboard Ridge, August headline MAE fell from **1,032.4 to 146.0 kW**, with R² increasing from **−1.761 to .746**. August broader-forward MAE fell from **1,512.9 to 615.8 kW**, but recorded-zero periods kept broader R² at only **.151**. June broader-forward MAE remained **3,268.1 kW** with R² **−1.237**. April improved, May changed little, and June headline improved; all counts and full metrics are in `label_assisted/label_assisted_development.csv`. The scenario is conditional on trustworthy recent power readings and verified latency, neither currently established.

## Interpretation and missing information

The data support a **source-level information gap**: independent engine/navigation signals can remain almost unchanged when all mechanical torquemeter channels abruptly switch to zero, and positive-power torque values shift across months at matched engine conditions. Model complexity alone has not recovered a stable mapping. This does not establish torquemeter calibration as the cause. Needed evidence is (1) torquemeter status/quality and calibration logs, export scale and N·m/kN·m convention; (2) independent shaft encoder or power measurement, clutch/gearbox/propulsion lineup and event logs; (3) trustworthy delayed power availability for an assisted design; (4) timestamped loading/draft/displacement reports with publication times; and (5) provider weather issue-versus-validity times before weather is used operationally.

## Reproduction and QA

V4 scripts are in `scripts/task3_v4/`; run `01_noon_eligibility.py`, `02_state_identifiability.py`, `03_state_transition_probs.py`, `04_boosting_development.py`, `05_label_assisted_scenario.py`, `06_compare_figures.py`, `08_stability_summary.py`, then `07_qa.py` from the project root. Dependencies are pinned in `scripts/task3_v4/requirements.txt`; installed CPU libraries were XGBoost 3.2.0, LightGBM 4.7.0 and CatBoost 1.2.10. The boosting runner saves and reuses each candidate-fold prediction rather than overwriting it if resumed. The final V4 QA run exited 0 with **16 PASS, 0 FAIL**, independently recomputing model and assisted metrics from saved predictions, checking timestamp/label pairing and enforcing the delayed-label window. No final report or December selection was produced.
