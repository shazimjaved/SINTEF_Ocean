# Task 3 technical appendix

This appendix records detailed numeric rows, methods of R² recovery and local reproducibility paths. It is separate from the 46-page academic report.

## Metric provenance

Direct rows use `sklearn.metrics.r2_score` on saved predictions and labels. August selection candidate predictions were not retained; their R² is recovered as `1 - n*RMSE²/SST` from the original full-precision RMSE and common August labels. No model was retrained.

| period             | scope           | model                             | method                                                | original_metrics_match     |     n |      mae_kw |     rmse_kw |   pearson_r |   r2_score |
|:-------------------|:----------------|:----------------------------------|:------------------------------------------------------|:---------------------------|------:|------------:|------------:|------------:|-----------:|
| august_final_refit | headline        | selected_model                    | direct_saved_predictions_sklearn                      | not_in_original_comparison | 35086 |  910.862317 | 1113.139767 |    0.837245 |  -2.185499 |
| august_selection   | headline        | A_restricted_onboard/histgb/15    | algebraic_from_original_rmse_no_candidate_predictions | rmse_identity_only         | 35086 |  942.513933 | 1137.316100 |    0.837453 |  -2.325373 |
| august_selection   | headline        | A_restricted_onboard/histgb/31    | algebraic_from_original_rmse_no_candidate_predictions | rmse_identity_only         | 35086 | 1042.189106 | 1199.709230 |    0.814914 |  -2.700241 |
| august_selection   | headline        | B_extended_onboard/histgb/31      | algebraic_from_original_rmse_no_candidate_predictions | rmse_identity_only         | 35086 | 1165.680101 | 1172.332715 |    0.989231 |  -2.533294 |
| august_selection   | headline        | B_extended_onboard/histgb/15      | algebraic_from_original_rmse_no_candidate_predictions | rmse_identity_only         | 35086 | 1165.860667 | 1172.367921 |    0.989577 |  -2.533507 |
| august_selection   | headline        | C_exploratory_weather/histgb/15   | algebraic_from_original_rmse_no_candidate_predictions | rmse_identity_only         | 35086 | 1173.543786 | 1178.761802 |    0.990956 |  -2.572154 |
| august_selection   | headline        | C_exploratory_weather/ridge/10.0  | algebraic_from_original_rmse_no_candidate_predictions | rmse_identity_only         | 35086 | 1186.635643 | 1191.355195 |    0.993075 |  -2.648888 |
| august_selection   | headline        | baseline/speed_cubic/train_only   | algebraic_from_original_rmse_no_candidate_predictions | rmse_identity_only         | 35086 | 1187.903162 | 1262.538849 |    0.727640 |  -3.097958 |
| august_selection   | headline        | C_exploratory_weather/histgb/31   | algebraic_from_original_rmse_no_candidate_predictions | rmse_identity_only         | 35086 | 1192.968806 | 1197.956663 |    0.990840 |  -2.689438 |
| august_selection   | headline        | C_exploratory_weather/ridge/100.0 | algebraic_from_original_rmse_no_candidate_predictions | rmse_identity_only         | 35086 | 1196.047296 | 1200.509088 |    0.993006 |  -2.705177 |
| august_selection   | headline        | B_extended_onboard/ridge/10.0     | algebraic_from_original_rmse_no_candidate_predictions | rmse_identity_only         | 35086 | 1213.980637 | 1217.379503 |    0.992529 |  -2.810044 |
| august_selection   | headline        | B_extended_onboard/ridge/100.0    | algebraic_from_original_rmse_no_candidate_predictions | rmse_identity_only         | 35086 | 1219.660246 | 1223.017359 |    0.992414 |  -2.845416 |
| august_selection   | headline        | A_restricted_onboard/ridge/100.0  | algebraic_from_original_rmse_no_candidate_predictions | rmse_identity_only         | 35086 | 1297.531052 | 1385.726470 |    0.630842 |  -3.936658 |
| august_selection   | headline        | A_restricted_onboard/ridge/10.0   | algebraic_from_original_rmse_no_candidate_predictions | rmse_identity_only         | 35086 | 1297.689409 | 1385.914841 |    0.630656 |  -3.938001 |
| august_selection   | headline        | baseline/training_mean/train_only | algebraic_from_original_rmse_no_candidate_predictions | rmse_identity_only         | 35086 | 1513.607690 | 1637.059401 |  nan        |  -5.889805 |
| sep_oct_stress     | headline        | selected_model                    | direct_saved_predictions_sklearn                      | True                       | 38517 |  884.104836 |  997.508667 |    0.923191 |   0.399389 |
| sep_oct_stress     | headline        | training_mean                     | direct_saved_predictions_sklearn                      | True                       | 38517 | 1599.967857 | 2023.727036 |  nan        |  -1.472088 |
| sep_oct_stress     | headline        | speed_cubic                       | direct_saved_predictions_sklearn                      | True                       | 38517 | 1387.121033 | 1649.877346 |    0.802597 |  -0.643098 |
| sep_oct_stress     | broader_forward | selected_model                    | direct_saved_predictions_sklearn                      | True                       | 52502 | 2009.798641 | 2839.175136 |    0.252914 |  -1.129182 |
| sep_oct_stress     | broader_forward | training_mean                     | direct_saved_predictions_sklearn                      | True                       | 52502 | 2555.849787 | 3189.894511 |  nan        |  -1.687701 |
| sep_oct_stress     | broader_forward | speed_cubic                       | direct_saved_predictions_sklearn                      | True                       | 52502 | 2334.859620 | 2922.514560 |    0.460873 |  -1.256014 |
| december_holdout   | headline        | selected_model                    | direct_original_predictions_sklearn                   | True                       | 39270 |  822.328930 | 1064.399922 |    0.003875 |  -7.952709 |
| december_holdout   | headline        | training_mean                     | direct_original_predictions_sklearn                   | True                       | 39270 | 2568.405065 | 2592.909858 |  nan        | -52.127530 |
| december_holdout   | headline        | speed_cubic                       | direct_original_predictions_sklearn                   | True                       | 39270 | 1944.204591 | 1989.114921 |    0.190518 | -30.265439 |
| december_holdout   | broader_forward | selected_model                    | direct_original_predictions_sklearn                   | True                       | 39313 |  823.843431 | 1066.836669 |    0.019947 |  -7.481470 |
| december_holdout   | broader_forward | training_mean                     | direct_original_predictions_sklearn                   | True                       | 39313 | 2571.322204 | 2597.271312 |  nan        | -49.270118 |
| december_holdout   | broader_forward | speed_cubic                       | direct_original_predictions_sklearn                   | True                       | 39313 | 1945.897216 | 1991.383772 |    0.212845 | -28.551885 |

## Target-conditional coverage

| split               |   calendar_minutes |   target_minutes |   forward_with_target |   headline_minutes |   forward_excluded_by_target_rule |   headline_pct_forward |   headline_pct_calendar |
|:--------------------|-------------------:|-----------------:|----------------------:|-------------------:|----------------------------------:|-----------------------:|------------------------:|
| jan_jun_train       |             262080 |           246767 |                184295 |             166154 |                             18141 |                 90.157 |                  63.398 |
| august_validation   |              44640 |            44640 |                 41205 |              35086 |                              6119 |                 85.150 |                  78.598 |
| sep_oct_stress      |              87840 |            54476 |                 52502 |              38517 |                             13985 |                 73.363 |                  43.849 |
| december_holdout    |              44640 |            44160 |                 39313 |              39270 |                                43 |                 99.891 |                  87.970 |
| july_quarantine     |              44640 |            44450 |                 23479 |              15398 |                              8081 |                 65.582 |                  34.494 |
| november_quarantine |              43200 |            42678 |                 25833 |              24691 |                              1142 |                 95.579 |                  57.155 |

## Distribution audit

| split               |      n |   target_mean_kw |   target_std_kw |   target_variance_kw2 |   stw_mean_kn |   stw_std_kn |   sog_mean_kn |   relative_wind_mean_kn |   relative_wind_missing |
|:--------------------|-------:|-----------------:|----------------:|----------------------:|--------------:|-------------:|--------------:|------------------------:|------------------------:|
| jan_jun_train       | 166154 |         5188.312 |        1188.132 |           1411656.750 |        11.770 |        1.943 |        11.571 |                  22.516 |                     336 |
| august_validation   |  35086 |         3674.490 |         623.688 |            388986.312 |        11.196 |        1.172 |        10.223 |                  20.534 |                       0 |
| sep_oct_stress      |  38517 |         3626.650 |        1287.139 |           1656727.750 |        11.496 |        1.219 |        11.001 |                  17.797 |                       2 |
| december_holdout    |  39270 |         2619.920 |         355.740 |            126551.203 |        10.472 |        0.942 |        10.111 |                  21.894 |                      94 |
| july_quarantine     |  15398 |         4077.444 |         666.802 |            444625.219 |        12.626 |        1.080 |        12.337 |                  25.423 |                       0 |
| november_quarantine |  24691 |         2331.271 |         515.558 |            265800.000 |        10.067 |        1.536 |         9.770 |                  16.636 |                       0 |

## Diagnostic bin coverage

| condition            |   headline_n |   binned_n |   missing_bin_n |   small_high_turn_bin_n |
|:---------------------|-------------:|-----------:|----------------:|------------------------:|
| relative_wind_kn     |        39270 |      39270 |              94 |                     nan |
| absolute_turn_degmin |        39270 |      39270 |               0 |                       8 |
| speed_over_ground_kn |        39270 |      39270 |               0 |                     nan |

## Scientific QA checklist

| id   | claim                                                                                               | status     | evidence                                                                                                                                                |
|:-----|:----------------------------------------------------------------------------------------------------|:-----------|:--------------------------------------------------------------------------------------------------------------------------------------------------------|
| SA01 | Frozen selection, model, original predictions and metric tables retain audited SHA256               | PASS       | verified=7 original artifacts                                                                                                                           |
| SA02 | Exact sklearn R² recomputation from saved August final-fit predictions                              | PASS       | r2_score=-2.185498782787                                                                                                                                |
| SA03 | All historical August candidate R² rows obey disclosed SSE/SST recovery identity                    | PASS       | selection rows=14; individual candidate predictions unavailable                                                                                         |
| SA04 | Exact sklearn R² for every December model and both scopes uses original predictions                 | PASS       | rows=6                                                                                                                                                  |
| SA05 | Original December MAE/RMSE and predictions remain numerically consistent                            | PASS       | All six original rows reconciled within 1e-5 kW                                                                                                         |
| SA06 | Exact sklearn R² for every stress model and both scopes uses saved frozen-model inference           | PASS       | rows=6                                                                                                                                                  |
| SA07 | Pearson r and R² are separate, non-interchangeable columns                                          | PASS       | Pearson r=0.003875; R²=-7.952709                                                                                                                        |
| SA08 | Saved August and December predictions align one-to-one with eligible timestamped labels             | PASS       | August=35086; December=39313                                                                                                                            |
| SA09 | Saved stress predictions align one-to-one with eligible timestamped labels                          | PASS       | stress=52502                                                                                                                                            |
| SA10 | Target-conditional headline and broader counts independently reconcile by split                     | PASS       | August, stress and December masks recomputed from saved minute tables                                                                                   |
| SA11 | Headline eligibility depends on unseen target fields and is identified as retrospective             | PASS       | The rule requires target minimum and negative-reading count                                                                                             |
| SA12 | Every diagnostic grouping accounts for all December headline observations                           | PASS       | Relative wind, turn, SOG, STW and daily totals each equal 39,270                                                                                        |
| SA13 | Relative-wind missing 94 and high-turn-rate n=8 are explicit and disclosed                          | PASS       | Missing relative wind=94; highest turn-rate bin=8                                                                                                       |
| SA14 | Post-freeze audit scripts contain no fitting calls and frozen split excludes December from training | PASS       | Audit code has no fit/partial_fit call; original model and selection hashes unchanged                                                                   |
| SA15 | Academic PDF and paginated Markdown contain exactly 46 pages                                        | PASS       | PDF=46 pages; Markdown=46 numbered sections with 45 page breaks                                                                                         |
| SA16 | Academic report separates Pearson r and R² and omits internal script paths                          | PASS       | Metric names distinct; internal script paths and agent history absent                                                                                   |
| SA17 | Direct sklearn R² for historical August candidate fits cannot be recomputed                         | UNRESOLVED | Individual selection-era candidate predictions and fitted candidate objects were not saved; algebraic R² from exact RMSE and common labels is disclosed |

## Reproduction

Run scripts 17, 18, 19 and 20 from the project root after the original frozen Task 3 experiment. Do not rerun the model-selection or December-evaluation scripts for this audit. The complete original experiment instructions remain in `outputs/task3/README.md`.

The academic report is generated from `outputs/task3/tables/metric_science_audit.csv`, `scope_coverage_audit.csv`, `split_distribution_audit.csv` and the saved figures. The original model and December predictions remain unchanged.
