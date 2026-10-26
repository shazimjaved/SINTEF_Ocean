# Task 3 scientific handoff for later tasks

The frozen experiment used January–June 2024 for training, August for model
selection, September–October for coverage stress, and December once as the
holdout. July and November remain target-quality quarantines. Only Ridge
Regression and HistGradientBoostingRegressor were trained as ML families;
training-mean and constrained speed-cubic models were baselines.

The selected restricted-onboard boosting model had August selection MAE
**942.5 kW**. Its saved final-fit August predictions give **910.9 kW MAE**,
Pearson **r = 0.837**, and **R² = −2.185**. December headline predictions give
**822.3 kW MAE**, **1,064.4 kW RMSE**, Pearson **r = 0.0039**, and **R² = −7.953**
on **39,270** minutes. Mean December residual (observed minus predicted) was
**−794.4 kW**. December observed mean/variance differ markedly from training
and August; target calibration, operating-state and covariate changes are
possible explanations, not established causes.

The headline subset is target-conditional: it requires positive target power
and no negative target reading within the minute. It cannot be identified at
inference time without knowing the target. Headline eligibility among forward
minutes with a target was **90.2%** in training, **85.1%** in August, **73.4%**
in September–October and **99.9%** in December. Broader forward-speed results
must accompany any headline metric, especially the stress-period MAE of
**2,009.8 kW** versus headline **884.1 kW**.

The original model, selection, December predictions and result tables remain
unchanged. A separate metric audit and 46-page academic report provide the
revised interpretation. Operational timing, weather issue-time semantics and
target calibration remain unresolved. December must not be used to tune this
experiment; a later untouched holdout is needed for any revised approach.
