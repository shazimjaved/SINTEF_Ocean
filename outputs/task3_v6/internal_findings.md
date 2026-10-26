# V6 internal chronological development experiment

**Question.** Does adding historical August to a January–June training history improve subsequent-period prediction? September and October were already inspected in V1/V5. They are development evaluations, **not fresh untouched holdouts**. No candidate, threshold, feature or parameter was chosen using their scores; December was not opened. July and November remain quarantined.

## Fixed design and provenance

The two histories are January–June and January–June plus August. Both predict September and October separately, with no September labels in the October fits. Four previously exercised full-history, label-free V2 onboard configurations were reused without retuning: restricted HGB (`A_hgb_full_v1like`), extended HGB (`B_hgb_full`), extended Ridge (`B_ridge_full`), and extended HGB trained on broad forward labels (`B_hgb_broad_full`). The latter receives historical zeros in fitting; it does **not** receive a target-derived state as an input. The original training-mean and nonnegative speed-cubic baselines were refitted for each history. All predictors are completed-minute onboard channels; no torquemeter, target, external weather or date-only Noon fields enter the feature arrays. Imputation and scaling remain within the saved training pipeline. The design was written to `experiment_manifest.json` before outputs were generated.

V4's recent-90-day variants are outside this comparison: a January–June-only arm would have **no** eligible training dates within 90 days of October. Using the V2 full-history variants keeps both training histories defined for both evaluation months without changing hyperparameters after inspecting their scores.

January–June supplies **166,154 positive** and **184,295 broader-forward** training minutes. Including August yields **201,240 positive** and **225,500 broader-forward** minutes. September supplies **16,798 positive**, **13,926 recorded-zero** and **36 negative/mixed** among **30,760** forward labelled minutes. October supplies **21,719 positive**, **12 zeros** and **11 negative/mixed** among **21,742**. September zeros account for **45.27%** of forward labelled minutes; October zeros are too few for a stable zero-specific comparison. The positive scope is retrospective and target-conditioned, not an inference-time eligibility rule.

## Main measured outcomes

The table shows the extended Ridge because it had the largest MAE response to adding August. **R is Pearson correlation**, kept separate from R². Bias is actual minus predicted, so a negative number indicates overprediction. Every other candidate, both baselines, all three scopes and exact values are in `development_metrics.csv` and `paired_training_history_comparison.csv`.

| Month | Scope | Training history | n | MAE kW | RMSE kW | R | R² | Bias kW |
|---|---|---|---:|---:|---:|---:|---:|---:|
| September | Positive | Jan–Jun | 16,798 | 1,111 | 1,115 | .977 | −6.115 | −1,111 |
| September | Positive | Jan–Jun + Aug | 16,798 | 564 | 586 | .932 | −.966 | −563 |
| September | Broader forward | Jan–Jun | 30,760 | 2,999 | 3,684 | .606 | −1.120 | −2,995 |
| September | Broader forward | Jan–Jun + Aug | 30,760 | 2,325 | 3,068 | .721 | −.470 | −2,323 |
| October | Positive | Jan–Jun | 21,719 | 925 | 927 | .971 | −17.863 | −925 |
| October | Positive | Jan–Jun + Aug | 21,719 | 329 | 354 | .858 | −1.746 | −327 |
| October | Broader forward | Jan–Jun | 21,742 | 926 | 928 | .956 | −15.356 | −924 |
| October | Broader forward | Jan–Jun + Aug | 21,742 | 329 | 354 | .873 | −1.387 | −327 |

Adding August reduced Ridge's overprediction level: mean positive predictions moved from **6,156 to 5,608 kW** in September against **5,044 kW** observed, and from **3,455 to 2,858 kW** in October against **2,530 kW** observed. Pearson R fell in both periods, so improved level does not imply improved tracking of minute-scale variation. All positive and broader-forward Ridge R² values remain negative. October positive target standard deviation is only about **213 kW**, making a residual ~327 kW bias substantial despite 329 kW MAE.

The response is **model dependent**. Restricted HGB improves September positive MAE from **676 to 569 kW** but worsens October from **1,045 to 1,074 kW**. Extended HGB improves September from **1,025 to 883 kW** and October from **858 to 814 kW**. Broad-trained HGB improves broader-forward September MAE from **2,991 to 2,286 kW** and October from **1,090 to 934 kW**, yet its September zero-specific MAE remains **3,764 kW**. August inclusion is therefore useful historical information for several fits, not a reliable zero-state solution or a uniformly beneficial update.

The existing simple baselines remain demanding. With August included, the September positive training-mean MAE is **232 kW** and speed-cubic MAE **404 kW**, both below Ridge's **564 kW**. On September broader forward, Ridge's **2,325 kW** is only about **37 kW** below the mean and speed-cubic comparators. October Ridge's **329 kW** is much lower than the corresponding mean **2,395 kW** and speed-cubic **1,823 kW**, but its negative R² precludes an accuracy claim relative to an October-specific oracle mean. Baseline-relative differences are in `baseline_relative_comparison.csv`.

## Daily stability and zero states

Among days with at least 30 labelled minutes, adding August lowers extended Ridge MAE on **13/13 September positive days**, **23/23 September broader-forward days**, and **16/16 October days** in both scopes. Median daily MAE changes are **−482, −673, −593 and −593 kW**, respectively. September broader-forward still has a worst daily MAE of **5,018 kW** after August, reflecting difficult recorded-zero runs. Daily results and pairwise day changes are in `daily_metrics.csv`, `daily_stability_summary.csv` and `daily_paired_improvement.csv`; the daily figure shows the temporal pattern.

For the **13,926 September recorded zeros**, the August-augmented Ridge predicts a mean **4,448 kW** and has **4,452 kW zero-specific MAE**. The broad-trained HGB reduces zero-specific MAE to **3,764 kW**, still far from zero. These scores diagnose an unresolved state-observability problem. They do not establish whether recorded zeros represent sensor failures or true shaft states. October has only 12 such readings, so no zero-state conclusion is drawn there.

## Reproduction and checks

From the project root, with versions in `scripts/task3_v6/requirements.txt`:

```text
python -X utf8 -B scripts/task3_v6/01_run_development.py
python -X utf8 -B scripts/task3_v6/02_figures.py
python -X utf8 -B scripts/task3_v6/03_qa.py
```

The first run fitted **eight pipelines** with at most two numerical-library threads; each recorded fit took **0.47–4.27 seconds** on the local CPU. Saved models and 24 timestamped prediction files are under `models/` and `predictions/`. A completed rerun preserves them and directs verification to QA. The scripts load compact monthly minute tables, not the full raw union. Peak memory was not instrumented. All three affected scripts exited **0**. Independent QA exited **0 with 17 PASS, 0 FAIL**: source-label alignment, exact metrics, daily counts/MAE/bias, split integrity and predictor provenance were checked. The Jan–Jun restricted HGB predictions exactly reproduce the archived V1 September–October predictions; both Jan–Jun baseline coefficients and combined stress metrics also reproduce V1.

The result supports **partial correction of a period-level prediction offset** when August history is available. It does not resolve September zero states, prove a stable physical target relationship, validate Noon timing, or create a fresh test set. A future prospective evaluation needs trustworthy shaft status/calibration metadata and a genuinely unseen period fixed before model choice.
