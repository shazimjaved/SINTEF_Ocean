# V8 internal reliability decision

**No new method meets the reliability gate.** Retain unchanged V7 calibrated Ridge as a conditional experimental reference, with persistence and history-mean comparators. Do not promote the cap, historical-risk flag or clipping as reliable transition repair. The main limitation is missing contemporaneous shaft-state information; this investigation does not establish a calibration defect or prove that every possible model must fail.

## Information audit

The four contracts are in `audit/information_availability.csv`; decisions and missing evidence are in `scenario_decisions.csv`. A uses only independent completed-minute onboard inputs. B additionally assumes trustworthy delayed labels, strictly earlier than covered-day midnight minus 24 hours, with daily refresh and a three-day history. Actual label issuance and latency remain unverified. C assumes only power is unavailable while valid synchronous torque/RPM remain available; it is a separate engineering diagnostic. D covers entire-package loss or coordinated recorded zeros and cannot obtain independent state information from those same missing/zero channels.

The actual preprocessing interval is **[end−1 minute, end)**. A V7 helper comment incorrectly described an inclusive right endpoint; this was a documentation discrepancy, not a change in aggregation code. Fully sampled representative raw power means match compact labels within **0.0051 kW**, consistent with CSV precision. No new preprocessing bug was identified here.

Raw June/August/September audits used three explicit registered QIDs, exact shared timestamps and no interpolation. The registered source for all three is **Instrument Torquemeter**. The numeric median factor P/(torque×RPM) is about **0.10472**, approximately **1,000 times** the factor for literal N·m, consistent with numeric torque behaving as kN·m. The registration still says **N*m**; it was not rewritten. The formula is not an exact independent identity: positive-triplet median absolute errors are 0.10/0.14/0.17 kW, mean errors 13.61/2.94/2.98 kW, with substantial tails. Shared processing/filtering or scaling conventions require vendor records, not a calibration diagnosis.

Only **21 June** exact timestamps had torque and RPM present but power missing; there were none in August/September. This does not establish operational availability during a future power-only outage. All June zero-power triplets also have zero torque/RPM, but some August/September zeros have one nonzero companion channel. Recorded zeros were never relabelled as missing or faulty. Multiplying minute mean torque by minute mean RPM is also not equivalent to averaging synchronous products: the representative-window discrepancy reaches about **804 kW**. Physics results are confined to audit files and never enter primary predictors, targets or ML benchmark scores.

## What the four V7 failures show

`audit/transition_case_minutes.csv.gz` records every prediction, source truth after scoring, independent conditions, legal cutoff, last available/admitted observation, state proportions, correction and label ages. The any-speed and admitted-forward last available readings coincide in these cases under the assumed latency.

| Case | Available history at first daily refresh | Interpretation from evidence | Frozen risk flag |
|---|---|---|---|
| June 12 zero block | Last label June 10 23:59: zero; 27.7% history zero, 72.3% positive; offset −160 kW | Three-day median retains the old positive level despite an available past zero. V7 MAE 5,812 kW, persistence zero. Avoidable smoothing failure, without proof of current physical state. | Abstains on all 60 minutes |
| June 18 zero block | Last label June 16 23:59: zero; history 100% zero; offset −6,213 kW | Engine RPM/speed are lower than the historical regime; the additive correction overshoots below zero. V7 MAE 2,568 kW. | Abstains on all 1,334 eligible truths |
| August 27 onset | First-day last label August 25 23:59: 3,435 kW; both daily histories are 100% positive | All **598 later zero truths** occur after the legal history cutoff while independent engine signals remain active. V7 block MAE 1,394 kW. Past state is stale and the permitted rules do not identify the new recorded state. | Accepts all 1,440 minutes, including all 598 severe zero errors |
| September 12 return to positive | Last label September 10 23:59: zero; history 100% zero; offset −4,792 kW | V7 underpredicts after a return to positive power; MAE 4,025 kW. A past zero cannot establish the current state. | Abstains on all 60 minutes |

Stale residual smoothing can sometimes be avoided with the already available past reading. A transition after the legal cutoff cannot be inferred merely by replacing one historical summary with another. Independent shaft/package status is needed to resolve that distinction reliably.

## Small predeclared ablation

Only April/May development folds set thresholds; Jan–Mar onboard data set the four feature scales. The frozen cap is **282.20 kW** (q95 absolute daily residual correction). Risk limits are early-fold q99 values for historical zero/negative proportions, residual MAD, label staleness, onboard drift and prediction disagreement; insufficient history/missing onboard inputs also trigger abstention. The **326.73 kW** early q95 absolute error is a reference for severe errors and an uncertainty envelope, not a guaranteed interval. June/August/September/October errors were not used to adjust rules. No threshold was revised after results.

On later V7 blocks, capping worsens broader MAE from **506 to 1,440 kW** and worsens the zero scope. Clipping lowers broader MAE to **283 kW** and eliminates negative predictions, but worst block MAE remains **5,812 kW**. It is only an optional nonnegative output constraint for an established physical scope; negative/mixed observations remain scored, not discarded.

The risk flag improves some selective averages by abstaining, but fails as a confidence guarantee. It accepts only 14.5% of later V7 zero truths—and **every accepted zero error exceeds the early reference**. On the new paired 24h windows it accepts 88.7% of positive truths with 72 kW MAE, yet also accepts **2,160 zero truths with 4,435 kW MAE**, all severe. Reporting the positive selective result alone would conceal this failure.

## Paired reconstruction evidence

Sixteen new 24h anchor unions, four each in June/August/September/October, were fixed by calendar date. The 1h/6h/24h scores use identical prediction prefixes. All maximum-horizon labels stay sealed, together with V7's earlier gaps, against every later fit/history. Four fresh **fixed-definition Ridge** fits were necessary for that new embargo; V7 weights were not changed. No other algorithm family was retrained. The common 24h embargo is conservative for a shorter outage whose observations might resume sooner.

| Horizon | Observed forward n | Zero n | V7-definition calibrated Ridge MAE kW | Capped MAE | Clipped MAE | Persistence MAE |
|---|---:|---:|---:|---:|---:|---:|
| 1h | 660 | 300 | 1,273 | 2,188 | 928 | 910 |
| 6h | 4,006 | 1,698 | 1,337 | 2,121 | 1,048 | 1,021 |
| 24h | 16,181 | 5,672 | 1,413 | 1,873 | 1,233 | 1,068 |

At 24h, unmodified calibration has **RMSE 2,399 kW, sklearn R² −.302, Pearson r .397, bias −399 kW**. Equal-block mean/p90/worst MAEs are **1,381/3,462/5,756 kW**. Persistence has lower pooled MAE and worst MAE **4,335 kW**, but is also unreliable at transitions. Capping does not improve this tradeoff. Clipping reduces negativity without resolving the high errors.

All 16 unions (23,040 calendar minutes) remain in coverage outputs; 12 have scoreable forward truth at 24h. There are **1,700 naturally missing eligible truths** at 24h. Eleven anchors have observed forward truth in every horizon; ten also have complete truth for all eligible minutes. Both matched sets are reported explicitly. The matched-any 24h calibrated MAE is **1,516 kW**, not an improvement hidden by selecting coverage. Primary eligibility uses finite STW≥3 only. The risk flag accepts **64.2% of operationally eligible 24h minutes**, or 70.9% of scoreable truths, and still misses severe zero-state errors. These are previously inspected development periods. Even matched prefixes contain different future operating minutes, so no causal duration-effect claim follows.

## Recommendation and reproduction

- **A:** Go as a research baseline; no-go for reliable transition/state inference.
- **B:** Conditional stable-regime research only; no-go for automatic reliable transition repair or confidence gating.
- **C:** Go for separate engineering diagnostics; no operational repair until torque scale, sensor location/filtering, issuance and outage validity are verified independently.
- **D:** No-go for reliable current power/state recovery from an absent/coordinated-zero shared package. Require independent shaft encoder/power or propulsion-line/clutch status and quality/event logs.

Retain the simpler V7 method and its original results as conditional references. No V8 method or final model is promoted. Required metadata include actual target delivery times, torquemeter health and zero-code conventions, torque-unit/export scale, sensor timing/filter definitions, and independent propulsion state. Historical-risk abstention is a warning mechanism, not proof that accepted states are safe.

Run from the project root with `scripts/task3_v8/requirements.txt`:

```text
python -X utf8 -B scripts/task3_v8/v8_common.py
python -X utf8 -B scripts/task3_v8/01_information_audit.py
python -X utf8 -B scripts/task3_v8/02_early_rules_ablation.py
python -X utf8 -B scripts/task3_v8/03_paired_reconstruction.py
python -X utf8 -B scripts/task3_v8/04_metrics_figures.py
python -X utf8 -B scripts/task3_v8/05_qa.py
```

The experimental scripts exited 0. Final scientific QA is **21 PASS, 0 FAIL**, including exact source alignment, earlier-only threshold provenance, strict label cutoffs, train-only imputation, global old/new gap exclusion, current-truth invariance, a hidden-label sentinel refit, matched denominators, exact metrics/tails and false-confidence accounting. A plot refresh reproduced every decoded CSV content hash; gzip container timestamps can change on regeneration, so byte equality of a regenerated gzip file alone is not a numeric reproducibility test. Hashes verify all 54 referenced V7 prediction files remain unchanged; source V7 model files predate V8. Full metrics, per-day/per-block errors, matched comparisons, negativity and accepted-error cases are under `tables/`; three diagnostic figures are under `figures/`. No December or quarantined monthly table was loaded. Original raw records and V1–V7 artifacts remain unchanged; no data were uploaded.
