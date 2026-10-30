# Internal Task 3 technical readiness

**Saved-output verification: PASS (13 PASS, 0 FAIL).**

This is an internal reproducibility note, not an academic report or client handover. No model was loaded, fitted, selected, or used to generate predictions.

## Completed checks

- Hashed 771 frozen project artifacts and five readiness implementation files; verified the 753-file pre-readiness preservation baseline.
- Recomputed 912 saved V6-V8 scope rows and 132 archived V1/V4 metric rows; reconciled missing-truth denominators and recorded-label error contributions.
- Reconstructed chronological training cutoffs and delayed-history ledgers; retained all 54 V7 blocks and 16 V8 paired anchors.
- Indexed all 62 output PNGs; 12 visually reviewed figures have mandatory captions that state scope and limitations.
- Validated notebook JSON and compiled every code cell. Standard Jupyter kernel execution was not run: `ipykernel` and `IPython` are unavailable locally.
- The original Task 3 requirement is reproducible notebooks/scripts; it does not require a notebook specifically. Existing scripts meet that form, and this notebook is an optional saved-evidence walkthrough.
- The local course rubric (`docs/2026_Lecture2_Dataset.pdf`) describes Task 3 methods, data preparation, baselines, validation, metrics, results and limitations, without prescribing Jupyter. Its written report section is not generated here because it is explicitly out of scope.

## Frozen interpretation

The current Task 3 scope is completed-minute, independent-onboard estimation of the registered recorded shaft-power channel with target-independent STW eligibility. Recorded zeros remain observed, quality-uncertain labels; no zero-as-missing conversion or target-based deployment gate is authorized. Positive-only/zero-excluded scores remain retrospective diagnostics. Label-assisted and simulated-gap results remain separate conditional scenarios. No universal all-regime winner is supported.

Within the paired V8 artificial-gap sample, delayed persistence has the lowest tested broad MAE at 1/6/24 h (~910/~1021/~1068 kW) versus calibrated Ridge (~1273/~1337/~1413 kW), but transitions remain unreliable. V7 October delayed-residual Ridge (~120 kW MAE) beats matched persistence/history means (~350/~329 kW), while September persistence (~956 kW) beats calibration (~1147 kW). These results rely on an unverified 24 h trustworthy-label assumption. The independent-sensor V6 comparison changes by month and scope; it does not support a single winner.

## Remaining limitations

- The notebook's standard Jupyter kernel path remains unverified. Install the pinned optional dependencies in `scripts/task3_readiness/requirements-jupyter.txt` in an authorized environment, then execute it there if required.
- No untouched labelled period or independent shaft-power reference remains available for a fresh generalization/physical-validity claim.
- V2-V4 historical estimator weights were not persisted; their saved predictions and metadata remain indexed. V6 saved vectors do not cover all eligible missing-truth minutes.
- Full raw-to-feature/model training reproduction was not run. Versioned scripts and environment pins are indexed; a clean-copy rebuild is not part of this readiness task.
- The final academic methods/results narrative remains deliberately unproduced; this pass delivers only internal technical readiness artifacts.

## Reproduction command

From the project root: `python -X utf8 -B scripts/task3_readiness/verify_saved_outputs.py`.
