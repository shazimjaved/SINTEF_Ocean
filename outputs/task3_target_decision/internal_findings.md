# INTERNAL target-cleaning and modelling-scope decision

**Recommendation:** preserve explicitly recorded zeros as observed,
quality-uncertain labels. Retain existing positive-trained models without
retraining. Freeze broader-forward recorded-channel evaluation with complete
coverage accounting, accompanied by positive-only and zero-exclusion
diagnostics. Next, consolidate the retained technical artifacts into one
current result/figure/run index and a verification entrypoint that requires no
training. No all-regime physical-power success is established.

## Evidence and label policy

The audit inspected original target-quality rules, V2/V3 zero diagnostics,
V6 training inventories and metrics, V7/V8 saved predictions, and the completed
source-provenance audit. Extracted supplied source documents contain no
definitive specification that zero power is a missing or invalid sentinel.
General missing-data/miscalibration warnings and planned challenge changes do
not establish that interpretation in this release. Metadata remains missing.

- **Absent:** no target observation in the completed minute (`target_n=0`,
  nonfinite target). Remains missing and unscoreable.
- **Positive:** existing positive scope requires mean>0, minimum>=0 and no
  negative raw sample. It is a recorded-label subset, not certified valid
  physical truth. It can include zero raw samples inside a positive-mean
  transition minute.
- **Zero:** observed mean=0 with no negative raw samples. Preserve the zero,
  source episode and retrospective quality flags. Active-engine/long-run flags
  indicate concern; they do not certify missingness or instrument failure.
- **Negative/mixed:** preserve negative means and nonnegative means containing
  negative raw samples separately from clean positive/zero labels. July and
  November remain quarantined for fitting/selection; existing counts are
  retained as context.

No labels, source flags or episodes were changed or filled with predictions.

## What was already tested

Positive-only fitting already underlies V1, the relevant V2/V3 Ridge variants,
and V6 restricted/extended positive-trained models. V6 also contains an existing
broad-trained HGB with the same settings as its positive-trained counterpart.
That comparison changes both zero and negative/mixed training labels; it is not
an isolated causal test of zero removal.

V2's positive-only recent Ridge still has approximately 1,032 kW August MAE;
V3's derived variant has 1,047 kW and negative R2. V6's Jan-Jun Ridge has
September/October positive MAE 1,111/925 kW. Including August reduces these to
564/329 kW, but both positive R2 values remain negative. Excluding zeros was
therefore already part of training and evaluation; another zero-excluded model
fit would not introduce the proposed new idea.

Historical positive filtering also changes temporal coverage: V6's Jan-Jun
positive fits end at the June 10 minute ending 10:41 UTC; their August-augmented
counterparts end August 27 at 20:02 UTC. Month names alone overstate label
recency. See `existing_fit_inventory.csv` and
`existing_positive_training_evidence.csv`.

## Paired saved-output results

Each row below rescored exactly the same saved predictions under nested label
scopes. No refitting, recalibration or prediction generation occurred.

| Existing method and sample | Broad MAE | Excluding recorded zeros MAE | Positive-only MAE | Positive R2 |
|---|---:|---:|---:|---:|
| V6 augmented Ridge, September | 2324.70 | 564.57 | 563.74 | -0.966 |
| V6 augmented Ridge, October | 329.21 | 329.01 | 328.80 | -1.746 |
| V7 delayed residual Ridge, September | 1147.14 | 1058.79 | 1059.96 | -20.863 |
| V7 delayed residual Ridge, October | 119.65 | 119.15 | 118.91 | +0.507 |
| V8 calibrated rule, paired 24h | 1413.32 | 537.65 | 537.11 | -0.613 |
| V8 persistence, paired 24h | 1068.12 | 720.53 | 718.98 | -1.362 |

Errors are kW. Zero exclusion retains negative/mixed observations, so it differs
from positive-only evaluation. `scope_metrics.csv` provides all MAE, RMSE,
sklearn R2, Pearson r, actual-minus-predicted bias, n and coverage by period.
`key_scope_comparisons.csv` is the compact main panel. No December predictions
were read or rescored. All later periods remain inspected development evidence.

The V8 ranking reverses across scopes: persistence wins broadly, calibration
wins on positive observations. Neither becomes a validated all-regime estimator.
The October gain survives zero exclusion; September positive failures also
survive. Positive-history-only V7 calibration already improves September
positive MAE to 237.93 kW while broad MAE is 2146.27 kW. That historical-label
sensitivity does not identify current state, and the corresponding V6 positive
training-mean baseline remains approximately 232 kW.

## Error accounting and coverage

For each model/period, positive, zero and negative/mixed groups partition n,
absolute error, squared error and signed error exactly. This is arithmetic
accounting of disagreements with recorded labels, not a causal decomposition
of sensor validity or an estimate of error against true physical power.

- V6 augmented Ridge in September: zeros are 45.27% of scoreable observations
  and contribute **86.71% of absolute error / 97.99% of squared error**.
- In October its zeros contribute only **0.12% / 0.22%**. The remaining bias
  cannot be explained by zero-state scoring.
- V7 September residual calibration: zeros contribute **49.49% / 43.13%**;
  substantial positive-state errors remain.
- V8 paired 24h calibrated rule: zeros contribute **75.29% / 77.44%**; positive
  MAE is still 537 kW and RMSE 1413 kW after they are excluded.

September has 31,729 target-independently eligible minutes: 30,760 observed
truths (96.95%), 969 missing truths, and only 16,798 clean positive truths
(52.94% of eligible minutes). October has 24,720 eligible minutes: 21,742
observed truths (87.95%), 2,978 missing, and 21,719 positive truths (87.86%).
V8 paired 24h has 17,881 eligible minutes: 16,181 observed (90.49%), 1,700
missing, and 10,504 positive truths (58.74%). These are different samples from
whole-month evaluations and cannot be ranked as equivalent tasks.

V6 saved outputs contain only observed forward truth rows. They cannot verify
prediction availability on its missing-truth minutes. V7/V8 retain eligible
missing-truth predictions; those remain unscoreable. All 54 V7 blocks are
retained, including unscoreable blocks, in `gap_block_metrics.csv`. Horizons
are kept separate; no causal duration-effect claim is made.

## Frozen modelling scope and delivery

The primary technical task is completed-minute independent-sensor estimation
of the registered recorded power channel under finite STW>=3 eligibility.
Broad-label errors assess agreement with an uncertain measurement record;
they do not certify physical-power error during questionable states. Positive
and zero-exclusion scores are secondary retrospective diagnostics. Historical
positive training is allowed as an explicit conditional fitting choice, but
current power positivity cannot be a deployment gate. Removing scored zeros
also leaves any effect of past zero labels on existing calibration unchanged.

Retain the original frozen independent-sensor reference and existing V6
history comparison. Keep V7 conditional label-assisted Ridge, matched
persistence/history mean, and simulated gaps in distinct information scenarios.
Keep physics reconstruction separate. No new winner, cleaning correction,
confidence rule or reliable state detector is selected here.

Task 3 already has preprocessing, features, simple baselines and several model
families, chronological experiments, required metrics, diagnostic figures and
pinned versioned scripts. Its requirements do not demand fabricated accuracy
or completion of the original challenge's fouling/deployment objectives.
`technical_delivery_checklist.csv` maps each requirement to existing evidence
and concrete remaining gaps. The next delivery work is a current artifact/run
index and consolidated saved-output verification entrypoint, with figure
captions and scope claims aligned to this decision. Independent target/status
metadata and fresh labelled validation remain external evidence gaps.

## Checks and reproducibility

**96 saved prediction files** were aligned with existing minute-table truth
and flags. Archived V6, V7 adaptation, V7 gap and V8 paired metrics reconcile
within numeric precision. Empty groups omitted by older summaries are retained
here with n=0. Constant-target sklearn R2 conventions are flagged and must not
be interpreted as skill. R2 changes between subsets also reflect a changed
target-variance denominator.

**15 checks PASS; 0 FAIL. All 753 pre-existing artifacts retain identical
SHA256 hashes**, including V1-V8 and the source audit. Only CSVs and this internal
note were saved here. No new model, source-data edit, report or handover was
created. Under the permitted output constraint, no new comparison script was
saved. Inputs, rules, category formulas, per-vector sums and file hashes are
recorded for an independent implementation of the consolidated verifier.
