# V7 internal experiment findings

The experiments are conditional on trustworthy shaft-power labels arriving 24 hours after their completed-minute timestamp. This availability and trust are **not established** for the vessel. September/October are previously inspected development periods. No December, July or November monthly tables were loaded, no final model was selected, and V1–V6/raw artifacts were left unchanged.

## Protocol and information available

**A, fixed label-free reference:** `a_reused_v6_metrics.csv` preserves all 72 V6 metric rows numerically. `a_prediction_provenance.csv` records hashes of its 24 original prediction files. Restricted HGB, extended Ridge/HGB, broad-trained HGB, mean and speed-cubic baselines retain their earlier definitions and training histories. No prior or contemporaneous target is an input feature.

**B, conditional adaptation:** V6 models trained on Jan–Jun+Aug predict September/October. Three fixed V2 model definitions are also updated for October with permitted September labels strictly before **2024-09-30 00:00 UTC**, available at the October 1 snapshot under the assumed delay. Daily residual correction uses the median of past actual-minus-fixed-predicted errors from **[day−4d, day−1d)**, with at least 30 observations. Persistence and a recent-history mean use the same visible history and cutoff. Daily refresh makes effective label age about 24–48 hours; no current-day labels are used. No-history cases retain the fixed prediction for residual correction and use the historical training mean for persistence/history mean. The minimum-30 rule does not weaken reported persistence: none of the scored cases has only 1–29 available history labels. A separate Ridge sensitivity admits only *past positive* labels, never current-target-based eligibility.

The fixed broad-label V6 model includes the August minute ending September 1 00:00. Its labels are not yet available for the first **1,440 September prediction rows** under the strict delay. B explicitly falls back to the older Jan–Jun model for those rows. Its September score therefore differs from the offline V6 broad-model score; this is an availability correction, not retuning. Positive-trained fixed models finish their training labels on August 27 and need no such fallback.

**C, missing-power reconstruction:** 54 nonoverlapping calendar windows were frozen before fitting: nine each in Apr/May/Jun/Aug/Sep/Oct, with 18 windows each of 1h, 6h and 24h. Placement uses dates, not target values. Every scheduled gap remains sealed permanently in all later C training/calibration/history, including when April enters the May training history. Models use chronological earlier permitted months with a 24-hour training-label cutoff at month start; residual histories use only visible out-of-training-period observations in the current month. The hidden truths are joined only after predictions are generated. Recorded zeros remain observed values; original missing readings remain missing. The experiment does not simulate a fault that corrupts the independent onboard inputs too.

Primary operational eligibility is **finite onboard STW≥3 kn**, independent of current power. Predictions are retained when truth is unavailable; only observed truths can be scored. Positive and recorded-zero scores are retrospective diagnostics. The B/C fitted models use V2's 24 extended onboard columns, with train-only imputation/scaling; A retains its existing 16-column restricted and 24-column extended sets. No shaft/torquemeter, Noon or external-provider variables enter those arrays. Predictions concern the completed minute at its end, not an earlier point within that minute.

## B: measured gains and failures

Primary broader-forward results below use the same observed eligible timestamps within each month. Bias is actual minus predicted. Full positive/zero/negative results for all fixed, updated and calibrated models are in `tables/b_adaptation_metrics.csv`. sklearn R² and Pearson r are separate metrics.

| Development period | Ridge scenario | n | MAE kW | RMSE kW | sklearn R² | Pearson r | Bias kW |
|---|---|---:|---:|---:|---:|---:|---:|
| September | Fixed through August | 30,760 | 2,325 | 3,068 | −.470 | .721 | −2,323 |
| September | Delayed residual, all recorded history | 30,760 | 1,147 | 1,916 | .427 | .684 | +40 |
| October | Fixed through August | 21,742 | 329 | 354 | −1.387 | .873 | −327 |
| October | Updated using permitted September | 21,742 | 260 | 292 | −.625 | .858 | −252 |
| October | Delayed residual, all recorded history | 21,742 | 120 | 152 | .558 | .852 | −50 |

The October residual correction improves positive-scope MAE from **329 to 119 kW**, R² from **−1.746 to .507**. It also beats the matched-history persistence (**350 kW broader MAE**) and history mean (**329 kW**). The monthly refit provides a smaller gain and retains negative R². These outcomes use extra historical labels and cannot be ranked as if they have the information available to A.

September exposes the cost of delayed state information. Broad residual calibration improves coverage of sustained recorded-zero runs, but **positive-only MAE worsens from 564 to 1,060 kW** (RMSE 1,955 kW) when the history still reflects zeros after positive power resumes. The matched-history persistence scores **956 kW broader MAE**, lower than residual correction's 1,147 kW, and **895 kW positive MAE**. Positive-history-only residual correction scores **238 kW positive MAE** but **2,146 kW broader MAE**; it does not solve zero states. The fixed positive-history training mean still scores **232 kW positive MAE** in September.

Among days with ≥30 observed eligible labels, October residual Ridge has median/worst broader daily MAE **106/236 kW**, versus fixed Ridge **329/444 kW** (16 days). September residual Ridge has median/worst **370/4,158 kW**, versus fixed **742/5,018 kW** (23 broader days). Its September positive worst day is **4,231 kW**. Daily metrics include all scored days; the ≥30 rule affects only the stability summary/display. There are **969 September** and **2,978 October** operationally eligible minutes with no scoreable target, retained in the prediction files and coverage table.

## C: sealed gaps and baseline comparisons

All **33,480 scheduled calendar minutes** are retained. There are **23,159 observed forward truths**: 19,031 positive, 4,122 zeros and six negative/mixed. Another **450 eligible minutes have naturally missing truth** and cannot be scored. Of 54 windows, **38 are scoreable** in the forward scope and **16 have no observed forward truth**; the latter are explicitly retained in `reconstruction/block_coverage.csv`. Source observation presence, vessel inactivity and missing data therefore constrain coverage.

| Gap duration | Observed forward n | Zero n | Fixed Ridge MAE kW | Residual Ridge MAE kW | Delayed persistence MAE kW | Delayed history mean MAE kW |
|---|---:|---:|---:|---:|---:|---:|
| 1h | 720 | 120 | 1,229 | 907 | 599 | 908 |
| 6h | 4,320 | 720 | 1,345 | 195 | 714 | 457 |
| 24h | 18,119 | 3,282 | 1,200 | 414 | 381 | 334 |

Full MAE/RMSE/R²/Pearson r/bias are in `tables/c_pooled_duration_metrics.csv`, with per-block, equal-block and daily stability alongside it. These durations use **different calendar and operating samples**. Their differences do not identify a causal gap-duration effect. The strong 6h result cannot be generalized to every six-hour outage.

Positive-scope residual Ridge MAE/RMSE are **489/1,278**, **117/167**, and **125/165 kW** at 1h/6h/24h. The 1h RMSE is worse than fixed Ridge (**657 kW**) despite a slightly lower MAE. At 24h, pooled history-mean MAE (**334 kW**) beats residual Ridge (**414 kW**); with equal weight per scoreable block the ordering reverses (**464 versus 411 kW**), so weighting and coverage must remain explicit.

Failures are substantial. The June 12 1h block contains 60 recorded-zero truths: residual Ridge MAE is **5,812 kW**, while persistence is zero. A three-day residual median can retain the earlier positive regime even when the last eligible historical label already records zero. The September 12 1h positive block has residual MAE **4,025 kW** after earlier zero history. The June 18 24h recorded-zero block has **2,568 kW** residual MAE, including negative predictions from the unbounded additive correction. The August 27 24h window crosses into zeros (842 positive, 598 zero minutes) and has residual MAE **1,394 kW**. No clipping, relabelling or removal was applied to improve these scores. None establishes whether the recorded zero represents a physical shaft state or a measurement failure.

## Execution, reproducibility and audit

Run from the project root using `scripts/task3_v7/requirements.txt`:

```text
python -X utf8 -B scripts/task3_v7/common.py
python -X utf8 -B scripts/task3_v7/01_adaptation.py
python -X utf8 -B scripts/task3_v7/02_reconstruction.py
python -X utf8 -B scripts/task3_v7/03_metrics_figures.py
python -X utf8 -B scripts/task3_v7/04_qa.py
```

All final commands exited **0**. Three October update pipelines and 12 reconstruction pipelines were fitted serially with two numerical threads; compact monthly tables were used instead of the raw sensor union. Completed experiment stages preserve their saved outputs on rerun. Models, per-minute predictions, history ledgers, fixed source hashes, all blocks and coverage are under `adaptation/` and `reconstruction/`; metrics and three diagnostic figures are under `tables/` and `figures/`.

Final QA is **21 PASS, 0 FAIL** in `v7_qa.csv`. It independently checks label/timestamp pairing, target-independent eligibility, training/history cutoffs, all hidden-label exclusions, exact metrics and daily results. Replacing hidden April targets with a huge sentinel and refitting the May Ridge leaves gap predictions unchanged. V6 prediction hashes remain unchanged.

The first QA result (18 PASS, 2 FAIL) is retained as `v7_qa_initial.csv`. Both mismatches concerned numeric storage: two copied V6 metric fields differ by ≤4.6e−13 after float64 CSV reserialization, and Ridge's float32 predictions must be restored as float32 for exact historical-residual replay. Saved model output dtypes were independently verified; `reconstruction/prediction_storage.json` and `numerical_precision_audit.csv` document the representation. Predictions, models and metric values were not altered to resolve these checks. Newly computed V7 metrics retain exact sklearn's finite R² convention for constant-zero scopes and flag `constant_target`; Pearson r is undefined there. A's archived V6 values remain unmodified. Those degenerate R² values should not be interpreted as skill.

Past-label information can improve stable-regime estimation and some missing-power windows under the stated assumption. Its failures during transitions, dependence on trustworthy labels, incomplete observation coverage and previously inspected evaluation periods prevent a claim of operational validity. Shaft-status and quality/calibration metadata plus verified label delivery timing remain necessary before deployment claims or a fresh prospective evaluation.
